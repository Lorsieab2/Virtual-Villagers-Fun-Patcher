"""Every grave in the Deaths log -- the graves no hook saw (all five games).

The owner: "two villagers are missing from the deaths log!" -- A New Home's
Kito and Chika were buried before v1.35.51 brought the Deaths log, so their
graves had no Death record -- and "make sure all the logs are consistent with
the current save".  At each save "VVFP Cause of Death.dll" hands every grave to
"VVFP Parentage Export.dll" (RecordGravesMissingFromLog), which writes a Death
record, from the grave, for each grave the village's Deaths log has none for:
the head, body, likes and dislikes from the villager's last Village History
snapshot (unknown when that does not settle who it was), and a note saying the
record was made from the grave.  Which graves are covered is kept in
"Virtual Villagers Fun Patcher Data\\Deaths\\Graves Logged - Save <n>.dat".

native/vvfp_cause_of_death/grave_backfill_harness.c drives the shipped
parentage DLL and the TEST build of the Cause of Death DLL in all five games'
geometry; see its header for the cases.
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
BUILD = ROOT / "scripts" / "build_grave_backfill_harness.ps1"
TEST_DLL = ROOT / "tests" / "test_dlls" / "VVFP Cause of Death.test.dll"
COD = ROOT / "native" / "vvfp_cause_of_death"
PARENTAGE = ROOT / "native" / "parentage_export"
CHECKS_PER_GAME = 37


class GraveBackfillSource(unittest.TestCase):
    def test_the_parentage_dll_exports_the_call(self):
        self.assertIn("RecordGravesMissingFromLog=_RecordGravesMissingFromLog@24",
                      (PARENTAGE / "parentage_export.def").read_text(encoding="utf-8"))
        self.assertIn('#include "grave_backfill.inc"',
                      (PARENTAGE / "parentage_export.c").read_text(encoding="utf-8"))

    def test_cause_of_death_exports_the_scan_and_the_answer(self):
        for name in ("vvfp_cause_of_death.def", "vvfp_cause_of_death_test.def"):
            text = (COD / name).read_text(encoding="utf-8")
            self.assertIn("VvfpCauseScanGraves=_VvfpCauseScanGraves@8", text)
            self.assertIn("VvfpCauseRepairGraves=_VvfpCauseRepairGraves@12", text)
        self.assertIn("SavedVillageHeader=_SavedVillageHeader@16",
                      (ROOT / "native" / "save_reset_export" / "save_reset_export.def").read_text(encoding="utf-8"))

    def test_only_a_record_on_disk_accounts_for_a_departure(self):
        # Codex, #524: a record from the grave that is only held for the save
        # (VV_GRAVE_QUEUED) is lost if the game ends first, so it must not
        # suppress the departed villager's Unaccounted record.
        source = (COD / "cod_backfill.inc").read_text(encoding="utf-8")
        save = source[source.index("static void backfill_at_save("):]
        save = save[:save.index("\n}\n")]
        gate = save[:save.index("recorded_now[recorded_now_count++] = i;")]
        gate = gate[gate.rindex("if ("):]
        self.assertEqual(gate.split("{")[0].strip(), "if (facts[i].outcome == VV_GRAVE_RECORDED)")

    def test_start_over_reserves_room_for_the_longest_file_name(self):
        # Codex, #524: wsprintfA has no bound, so the reserve vv_reset_slot_state
        # asks of the save folder must cover the longest name it formats -- the
        # graves file, now longer than the parentage sidecar.
        import re as _re
        source = (ROOT / "native" / "shared" / "save_reset.c").read_text(encoding="utf-8")
        state = source[source.index("int vv_reset_slot_state("):]
        reserve = state[state.index("if (!vv_save_folder(folder, (int)sizeof("):]
        reserve = reserve[:reserve.index(")))")]
        literal = "".join(_re.findall(r'"((?:[^"\\]|\\.)*)"', reserve)).replace("\\\\", "\\")
        logged = source[source.index("#define GRAVES_LOGGED_FORMAT(n)"):]
        logged = logged[:logged.index("#define SIDECAR_FORMAT_COUNT")]
        name = "".join(_re.findall(r'"((?:[^"\\]|\\.)*)"', logged)).replace("\\\\", "\\")
        suffix = name.replace("%s", "").replace("%d", "0")      # the game digit `n` is one more
        self.assertGreaterEqual(len(literal), len(suffix) + 1)
        self.assertIn("Graves Logged - Save 0.dat", literal)

    def test_nothing_is_written_without_repair(self):
        source = (COD / "cod_backfill.inc").read_text(encoding="utf-8")
        save = source[source.index("static void backfill_at_save("):]
        save = save[:save.index("\n}\n")]
        self.assertIn("!repair_chosen[slot]", save)
        scan = source[source.index("VvfpCauseScanGraves(int game, int slot)"):]
        scan = scan[:scan.index("\n}\n")]
        self.assertIn("record_graves(g_game, NULL, slot, facts, count, 0)", scan)
        self.assertNotIn("logged_publish", scan)

    def test_the_backfill_runs_at_the_save_before_the_reconciliation(self):
        roster = (COD / "cod_roster.inc").read_text(encoding="utf-8")
        done = roster[roster.index("static void cod_save_done("):]
        done = done[:done.index("\n}\n")]
        self.assertLess(done.index("cod_publish_village(save_buffer, slot);"),
                        done.index("backfill_at_save(slot, save_buffer);"))
        self.assertLess(done.index("backfill_at_save(slot, save_buffer);"),
                        done.index("roster_reconcile(slot);"))

    def test_a_burial_record_is_never_taken_as_coverage_on_trust(self):
        # Codex, #524: a burial's record may only be held for the save, so
        # its grave is checked against the log on disk like any other.
        for name in ("cod_vv12.inc", "cod_vv345.inc", "cod_backfill.inc", "vvfp_cause_of_death.c"):
            self.assertNotIn("backfill_mark", (COD / name).read_text(encoding="utf-8"))

    def test_the_data_file_has_its_own_folder_and_one_path_helper(self):
        source = (COD / "cod_backfill.inc").read_text(encoding="utf-8")
        self.assertIn('wsprintfA(stem, "Virtual Villagers %d Graves Logged", g_game);', source)
        self.assertIn('cod_data_path(logged.path, "Deaths", stem, slot)', source)
        self.assertEqual(source.count("vv_save_subfolder("), 1)

    def test_start_over_forgets_the_slot(self):
        source = (COD / "vvfp_cause_of_death.c").read_text(encoding="utf-8")
        reset = source[source.index("VvfpCauseVillageReset(int game, int slot)"):]
        self.assertIn("backfill_reset(slot);", reset[:reset.index("\n}\n")])


@unittest.skipUnless(CL.is_file(), "the 32-bit MSVC toolchain is not installed")
@unittest.skipUnless(TEST_DLL.is_file(), "test builds are not in the release source archive (tests/test_dlls)")
class GraveBackfillHarness(unittest.TestCase):
    def test_the_harness_passes_in_all_five_games(self):
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(BUILD)],
            capture_output=True, text=True, timeout=600,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("== 0 failure(s) ==", result.stdout)
        for game in range(1, 6):
            self.assertIn(f"Virtual Villagers {game}\n", result.stdout)
        self.assertEqual(len(re.findall(r"^  ok ", result.stdout, re.M)), 5 * CHECKS_PER_GAME, result.stdout)


if __name__ == "__main__":
    unittest.main()
