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
        self.assertIn('#define DEATHS_FOLDER L"Virtual Villagers Fun Patcher Logs\\\\Deaths"', source)
        for n in range(1, 6):
            self.assertIn(f'L"Virtual Villagers {n} Deaths Log"', source)
        self.assertIn('return family == LOG_DEATHS ? "Death "', source)
        self.assertIn(': family == LOG_UNACCOUNTED ? "Unaccounted " : "Conception ";', source)
        self.assertIn('#define UNACCOUNTED_FOLDER L"Virtual Villagers Fun Patcher Logs\\\\Unaccounted Villagers"', source)
        self.assertIn("return emit_record(game_id, kind, check ? records : NULL, text);", source)

    def test_start_over_sweeps_the_logs_and_the_companion_files(self):
        source = RESET.read_text(encoding="utf-8")
        self.assertIn('L"Virtual Villagers Fun Patcher Logs\\\\Deaths"', source)
        self.assertIn('L"Virtual Villagers Fun Patcher Logs\\\\Unaccounted Villagers"', source)
        self.assertIn("for (pass = 0; pass < 6; ++pass) {", source)
        self.assertRegex(source, r'CAUSE_OF_DEATH_FORMAT\("1"\),\s+ROSTER_FORMAT\("1"\), GRAVES_LOGGED_FORMAT \}')
        self.assertRegex(
            source, r'CAUSE_OF_DEATH_FORMAT\("2"\),\s+ROSTER_FORMAT\("2"\), GRAVES_LOGGED_FORMAT, 0, 0, 0, 0 \}')
        for n in (3, 4, 5):
            self.assertRegex(source, rf'ROSTER_FORMAT\("{n}"\),\s+GRAVES_LOGGED_FORMAT, 0, 0, 0, 0, 0 \}}')
        # The grave backfill's file (cod_backfill.inc) goes with the Deaths log.
        self.assertIn('"%s\\\\Virtual Villagers Fun Patcher Data\\\\Deaths\\\\Graves Logged - Save %d.dat"', source)
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
        self.assertEqual(len(re.findall(r"^  ok ", result.stdout, re.M)), 138, result.stdout)

    @unittest.skipUnless(TEST_DLL.is_file(), "test builds are not in the release source archive (tests/test_dlls)")
    def test_the_graves_file_harness_passes_against_the_test_build(self):
        result = run("build_cause_files_harness.ps1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASSED: 0 failure(s)", result.stdout)
        self.assertEqual(len(re.findall(r"^  ok ", result.stdout, re.M)), 46, result.stdout)


if __name__ == "__main__":
    unittest.main()
