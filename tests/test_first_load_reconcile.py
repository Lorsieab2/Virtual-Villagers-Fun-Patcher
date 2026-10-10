"""The first-load reconcile of the Village Elders and Village Statistics files.

The owner (2026-10-04): "I want everything to reconcile with the game saves."
"VVFP Statistics Export.dll" (native/statistics_export/statistics_reconcile.inc)
puts right what the save and the patcher's own logs PROVE about the two files
it keeps per slot -- elders the Village History log shows with Master in three
or more skills who are missing from the list; Villagers Buried, The Lost
Children's Twins Birthed and The Secret City's Chiefs Robed below what the
Deaths log, the memorial, the Births log or a living chief prove -- only after
the first-load prompt's Repair, at the next save, backed up and listed in the
Repairs log, never lowering a counter or removing an elder.

native/statistics_export/reconcile_harness.c drives the TEST build of the DLL
in all five games' geometry; see its header for the cases.
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
BUILD = ROOT / "scripts" / "build_reconcile_harness.ps1"
TEST_DLL = ROOT / "tests" / "test_dlls" / "VVFP Statistics Export.test.dll"
STATS = ROOT / "native" / "statistics_export"
SHARED = ROOT / "native" / "shared"
# 106 checks across the five games (19 to 25 each; New Believers' elders since the History's Faction line).
# 7: Repair right after the quit save, every game; 0: the memorial at the load (VV1, VV2);
# 8: Deaths logs in both the old and the new folder, every game (2 each).
CHECKS = 106 + 8 * 5 + 2 + 2 * 5


def body(source: str, head: str) -> str:
    text = source[source.index(head):]
    return text[:text.index("\n}\n")]


class ReconcileSource(unittest.TestCase):
    def test_the_dll_exports_the_scan_and_the_answer(self):
        text = (STATS / "statistics_export.def").read_text(encoding="utf-8")
        self.assertIn("VvfpStatisticsScanReconcile=_VvfpStatisticsScanReconcile@16", text)
        self.assertIn("VvfpStatisticsRepairReconcile=_VvfpStatisticsRepairReconcile@12", text)
        self.assertNotIn("TestSave", text)
        test = (STATS / "statistics_export_test.def").read_text(encoding="utf-8")
        self.assertIn("VvfpStatisticsTestSave=_VvfpStatisticsTestSave@12", test)

    def test_nothing_changes_without_repair_and_only_on_the_same_villages_flushed_save(self):
        source = (STATS / "statistics_reconcile.inc").read_text(encoding="utf-8")
        apply = body(source, "static int rc_apply(")
        self.assertIn("!g_rc_save_ok", apply)
        self.assertIn("!g_rc_repair[slot]", apply)
        export = (STATS / "statistics_export.c").read_text(encoding="utf-8")
        save = body(export, "__declspec(dllexport) int __stdcall SaveVillageStatistics(")
        self.assertIn("g_rc_save_ok = changed == ROSTER_SAME && (flushed & 1) != 0;", save)
        write = body(export, "__declspec(dllexport) int __stdcall WriteVillageStatistics(")
        # After the living-elder update, before the log is written.
        self.assertLess(write.index("village_elders_for(game_id);"), write.index("rc_apply(game_id, save_id, manager);"))
        self.assertLess(write.index("rc_apply(game_id, save_id, manager);"), write.index("write_statistics_file("))
        scan = body(source, "VvfpStatisticsScanReconcile(int game, int slot, char *text, int cap)")
        self.assertIn("if (roster != ROSTER_SAME)", scan)
        for writer in ("rc_write_elders", "vvs_counter_raise", "vv_repairs_note", "vv_repair_backup"):
            self.assertNotIn(writer, scan)

    def test_the_note_comes_before_the_change_and_backups_never_replace(self):
        source = (STATS / "statistics_reconcile.inc").read_text(encoding="utf-8")
        apply = body(source, "static int rc_apply(")
        self.assertLess(apply.index("vv_repair_backup(g_store.counters_path"), apply.index("vv_repairs_note("))
        self.assertLess(apply.index("vv_repairs_note("), apply.index("rc_write_elders(slot, &plan)"))
        self.assertLess(apply.index("vv_repairs_note("), apply.index("vvs_counter_raise("))
        log = (SHARED / "repairs_log.h").read_text(encoding="utf-8")
        self.assertIn("CopyFileW(path, backup, TRUE)", log)
        self.assertIn('L".before-v1.35.58-repair"', log)

    def test_a_counter_is_never_lowered(self):
        store = (STATS / "statistics_store.c").read_text(encoding="utf-8")
        raise_ = body(store, "int vvs_counter_raise(")
        self.assertIn("if (e->value >= to) {", raise_)

    def test_heathens_and_the_lost_children_are_never_given_history_elders(self):
        source = (STATS / "statistics_reconcile.inc").read_text(encoding="utf-8")
        plan = body(source, "static void rc_make_plan(")
        self.assertIn("if (game == GAME_VV1 || game == GAME_VV3 || game == GAME_VV4 || game == GAME_VV5) {", plan)
        self.assertIn("h.master = game == GAME_VV1 ? 90 : 88;", plan)
        # New Believers: only a snapshot's "Faction: Believer" villager (Heathens never count).
        counted = body(source, "static int rc_counted(")
        self.assertIn("return skills > 0 && (h->game != GAME_VV5 || faction == 1);", counted)
        visit = body(source, "static void rc_visit_history(")
        self.assertIn('strcmp(line, "  Faction: Believer") == 0', visit)
        self.assertEqual(visit.count("rc_counted(h, skills, faction)"), 2)
        # ...the line the History and Population records carry, worded as the Unaccounted record's.
        exporter = (ROOT / "native" / "population_export" / "population_export.c").read_text(encoding="utf-8")
        self.assertIn('fprintf(file, "  Faction: %s\\n", record[VV5_FACTION] != 0 ? "Heathen" : "Believer")', exporter)
        roster = (ROOT / "native" / "vvfp_cause_of_death" / "cod_roster.inc").read_text(encoding="utf-8")
        self.assertIn('"  Faction: Heathen\\n" : "  Faction: Believer\\n"', roster)


@unittest.skipUnless(CL.is_file(), "the 32-bit MSVC toolchain is not installed")
@unittest.skipUnless(TEST_DLL.is_file(), "test builds are not in the release source archive (tests/test_dlls)")
class ReconcileHarness(unittest.TestCase):
    def test_the_harness_passes_in_all_five_games(self):
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(BUILD)],
            capture_output=True, text=True, timeout=600,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"== {CHECKS} check(s), 0 failure(s) ==", result.stdout)
        for game in range(1, 6):
            self.assertIn(f"Virtual Villagers {game}\n", result.stdout)
        self.assertEqual(len(re.findall(r"^  ok ", result.stdout, re.M)), CHECKS, result.stdout)


if __name__ == "__main__":
    unittest.main()
