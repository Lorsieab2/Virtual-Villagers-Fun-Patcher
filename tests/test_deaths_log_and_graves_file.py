"""The Deaths and Unaccounted Villagers logs and the Cause of Death files, on
real files.

Two 32-bit native harnesses drive the real DLLs against files on disk under a
throwaway save folder named after the harness:

* native/parentage_export/death_log_harness.c -- the shipped "VVFP Parentage
  Export.dll" (WriteVillageRecord): in all five games' record geometry, a
  "Death <n>" record in ONE format (name, age at death in the game's own
  units, cause, grave, epitaph, head, body, likes, dislikes), "Disappeared"
  and "Epitaph changed" unnumbered in the Deaths log, "Unaccounted <n>" in
  its own log; both logs created at a village's save (only when "VVFP Cause
  of Death.dll" ships), a record before the first save held and filed under
  the village, a record outside the game's table or a kind out of range
  refused, 256 Death records per file, and Start Over deleting that
  village's logs and no other's.
* native/vvfp_cause_of_death/cause_files_harness.c -- the TEST build of
  "VVFP Cause of Death.dll": the per-slot graves file's exact bytes (the
  player's own epitaph included), written atomically, read back by a new
  session, deaths before the slot is known kept, slots never mixed, an
  unreadable file set aside and a locked one left alone, Start Over
  forgetting the slot before the reset deletes the file; and the village
  roster's reconciliation at each save (nothing at the first save, one
  record per unreported departure or arrival, nothing for a reload's packing
  of the records, for reported departures and arrivals, or for another
  village's roster; a record freed by a reported burial or removal and then
  filled by a newcomer nobody reported -- of the same sex, or the buried
  villager's own bytes written back -- is one record, while a reported
  birth into it, a body kept or revived, and the reload after burials are
  nothing).

The harnesses need the 32-bit MSVC toolchain, so they run where it is
installed and are skipped elsewhere. The static checks run everywhere.
"""
from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CL = Path(
    r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC"
    r"\14.51.36231\bin\Hostx64\x86\cl.exe"
)
PARENTAGE = ROOT / "native" / "parentage_export" / "parentage_export.c"
RESET = ROOT / "native" / "shared" / "save_reset.c"
TEST_DLL = ROOT / "tests" / "test_dlls" / "VVFP Cause of Death.test.dll"


def run(script: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts" / script)],
        capture_output=True, text=True, timeout=600,
    )


class DeathsLogSource(unittest.TestCase):
    def test_deaths_have_their_own_folder_stem_and_marker(self):
        source = PARENTAGE.read_text(encoding="utf-8")
        # "Deaths and Disappearances" (the owner, 2026-10-09), named in native/shared/save_layout.h with
        # the folder's older name: an older build's "Deaths" is written where it is while only it
        # exists, and nothing is ever moved.
        self.assertIn("vv_layout_dir_rel_w(root, VV_DEATHS_LOGS_OLD, VV_DEATHS_LOGS_DIR)", source)
        self.assertIn("return family == LOG_DEATHS ? deaths_folder()", source)
        self.assertNotIn("vv_layout_move", source)
        layout = (ROOT / "native" / "shared" / "save_layout.h").read_text(encoding="utf-8")
        self.assertIn('#define VV_DEATHS_LOGS_DIR VV_LOGS_DIR L"\\\\Deaths and Disappearances"', layout)
        self.assertIn('#define VV_DEATHS_LOGS_OLD VV_LOGS_DIR L"\\\\Deaths"', layout)
        for n in range(1, 6):
            self.assertIn(f'L"Virtual Villagers {n} Deaths Log"', source)
        self.assertIn('return family == LOG_DEATHS ? "Death "', source)
        self.assertIn(': family == LOG_UNACCOUNTED ? "Unaccounted "', source)
        self.assertIn(': family == LOG_EVENTS ? "Island event " : "Conception ";', source)
        self.assertIn('#define UNACCOUNTED_FOLDER L"Virtual Villagers Fun Patcher Logs\\\\Unaccounted Villagers"', source)
        self.assertIn("return emit_record(game_id, kind, check ? records : NULL, text);", source)

    def test_start_over_sweeps_the_logs_and_the_companion_files(self):
        source = RESET.read_text(encoding="utf-8")
        # The Deaths logs' folder by its new name and, while an older build's has not moved, its old one.
        self.assertIn('L"Virtual Villagers Fun Patcher Logs\\\\Deaths and Disappearances"', source)
        self.assertIn('L"Virtual Villagers Fun Patcher Logs\\\\Deaths"', source)
        self.assertIn('L"Virtual Villagers Fun Patcher Logs\\\\Unaccounted Villagers"', source)
        self.assertIn('L"Virtual Villagers Fun Patcher Logs\\\\Island Events"', source)
        self.assertIn("for (pass = 0; pass < 8; ++pass) {", source)
        # Each kind in its own folder (native/shared/data_subfolder.h), and
        # the loose name an older build wrote: both are the village's.
        for n in (1, 2):
            self.assertRegex(source, r'DATA_FORMAT\(VV_DATA_SUB_GRAVES, "Virtual Villagers %d Graves"\), '
                                     r'CAUSE_OF_DEATH_FORMAT\("%d"\)' % (n, n))
        # The roster by its new name, "Villagers at Last Save", and an older build's "Village Roster".
        for n in range(1, 6):
            self.assertRegex(source, r'DATA_FORMAT\(VV_DATA_SUB_UNACCOUNTED, "Virtual Villagers %d Villagers at Last Save"\),'
                                     r'\s+DATA_FORMAT\(VV_DATA_SUB_UNACCOUNTED, "Virtual Villagers %d Village Roster"\),'
                                     r'\s+ROSTER_FORMAT\("%d"\)' % (n, n, n))
        # The grave backfill's file (cod_backfill.inc) goes with the Deaths log.
        for n in range(1, 6):
            self.assertRegex(source, r'ROSTER_FORMAT\("%d"\), GRAVES_LOGGED_FORMAT\("%d"\)' % (n, n))
        self.assertIn('"%s\\\\Virtual Villagers Fun Patcher Data\\\\Deaths\\\\Virtual Villagers " n " Graves Logged - Save %d.dat"', source)
        self.assertIn('" Graves - Save %d.dat"', source)
        self.assertIn('" Village Roster - Save %d.dat"', source)

    def test_the_folders_are_spelled_out(self):
        for path in (PARENTAGE, RESET, ROOT / "native" / "vvfp_cause_of_death" / "vvfp_cause_of_death.c"):
            self.assertNotRegex(path.read_text(encoding="utf-8"), r'"VVFP Logs\\\\Deaths')


@unittest.skipUnless(CL.is_file(), "the 32-bit MSVC toolchain is not installed")
class Harnesses(unittest.TestCase):
    def test_the_deaths_log_harness_passes_against_the_shipped_dll(self):
        result = run("build_death_log_harness.ps1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("== 0 failure(s) ==", result.stdout)
        # 212, and 4 for an older build's "Deaths" beside "Deaths and Disappearances" (the owner,
        # 2026-10-09: old and new names alike): numbered after the highest in either folder; and 20 for
        # "Lost before birth" (4 in each game); and 2 for two deaths in a row with both folders there (the
        # owner's A New Home: four records all "Death 15").
        self.assertEqual(len(re.findall(r"^  ok ", result.stdout, re.M)), 238, result.stdout)
        self.assertIn("  ok   numbered Death 6 and Death 7 after the older folder's Death 5, never Death 6 twice", result.stdout)
        self.assertIn("  ok   written in Deaths and Disappearances as Death 6, after the older folder's Death 5",
                      result.stdout)
        self.assertIn("  ok   the older folder's log is untouched", result.stdout)

    @unittest.skipUnless(TEST_DLL.is_file(), "test builds are not in the release source archive (tests/test_dlls)")
    def test_the_graves_file_harness_passes_against_the_test_build(self):
        result = run("build_cause_files_harness.ps1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASSED: 0 failure(s)", result.stdout)
        # 58, and 4 for the roster's older name in its folder (native/shared/save_layout.h): used under
        # that name, loose or in its folder, never moved or renamed
        self.assertEqual(len(re.findall(r"^  ok ", result.stdout, re.M)), 62, result.stdout)
        self.assertIn("  ok   the save read and wrote it under its older name, never renaming it: nobody unaccounted",
                      result.stdout)
        self.assertIn("  ok   the save used the roster where an older build left it (loose, by its older name), never moving it",
                      result.stdout)


if __name__ == "__main__":
    unittest.main()
