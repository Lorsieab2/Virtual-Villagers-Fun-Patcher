""""Arrived" records in the Births and Conceptions log (all five games).

The owner (2026-10-04): every grown villager who joins a village -- an island
event's newcomer, the Custom Island Event's new villagers, the Barrel O'
Babies, ... -- gets an "Arrived" record in the Births and Conceptions log, in
all five games and in one format; villagers already in a village who arrived
before the record existed get one backfilled, but only after the first-load
prompt's Repair, exactly once.

"VVFP Cause of Death.dll" sees the arrivals (cod_arrivals.inc) and "VVFP
Parentage Export.dll" files the records (KIND_ARRIVED, arrival_backfill.inc);
native/shared/arrival_backfill.h has the format.
native/vvfp_cause_of_death/arrival_harness.c drives the shipped parentage and
Save Reset DLLs and the TEST build of the Cause of Death DLL in all five
games' geometry; see its header for the cases.
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
BUILD = ROOT / "scripts" / "build_arrival_harness.ps1"
TEST_DLL = ROOT / "tests" / "test_dlls" / "VVFP Cause of Death.test.dll"
COD = ROOT / "native" / "vvfp_cause_of_death"
PARENTAGE = ROOT / "native" / "parentage_export"
SHARED = ROOT / "native" / "shared"
# 27 in every game, one more in A New Home (no Show Parents), two more in New
# Believers (the Heathens).
CHECKS = 27 * 5 + 1 + 2


def body(source: str, head: str) -> str:
    text = source[source.index(head):]
    return text[:text.index("\n}\n")]


class ArrivedRecordSource(unittest.TestCase):
    def test_the_dlls_export_the_calls(self):
        self.assertIn("RecordArrivalsMissingFromLog=_RecordArrivalsMissingFromLog@24",
                      (PARENTAGE / "parentage_export.def").read_text(encoding="utf-8"))
        for name in ("vvfp_cause_of_death.def", "vvfp_cause_of_death_test.def"):
            text = (COD / name).read_text(encoding="utf-8")
            self.assertIn("VvfpCauseScanArrivals=_VvfpCauseScanArrivals@8", text)
            self.assertIn("VvfpCauseRepairArrivals=_VvfpCauseRepairArrivals@12", text)
            self.assertIn("VvfpCauseArrivedBy=_VvfpCauseArrivedBy@12", text)

    def test_the_record_is_numbered_on_its_own_and_never_rolls(self):
        source = (PARENTAGE / "parentage_export.c").read_text(encoding="utf-8")
        self.assertIn("KIND_EPITAPH = 4, KIND_UNACCOUNTED = 5, KIND_ARRIVED = 6", source)
        self.assertIn('fprintf(file, "Arrived %d\\n%s", arrived_before + 1, text)', source)
        numbered = body(source, "static int kind_is_numbered(int kind) {")
        self.assertNotIn("KIND_ARRIVED", numbered)
        self.assertIn('strncmp(line, "Arrived ", 8) == 0', body(source, "static int read_log_header("))

    def test_nothing_is_backfilled_without_repair(self):
        source = (COD / "cod_arrivals.inc").read_text(encoding="utf-8")
        save = body(source, "static void arrival_backfill_at_save(")
        self.assertIn("!arrivals_repair[slot]", save)
        self.assertIn("vv_arrival_marker_present(g_game, slot)", save)
        scan = body(source, "VvfpCauseScanArrivals(int game, int slot)")
        self.assertIn("record_arrivals(g_game, NULL, slot, arrival_facts, count, 0)", scan)
        self.assertNotIn("marker_write", scan)

    def test_the_backfill_runs_at_the_save_before_the_reconciliation(self):
        roster = (COD / "cod_roster.inc").read_text(encoding="utf-8")
        done = body(roster, "static void cod_save_done(")
        self.assertLess(done.index("backfill_at_save(slot, save_buffer);"),
                        done.index("arrival_backfill_at_save(slot, save_buffer);"))
        self.assertLess(done.index("arrival_backfill_at_save(slot, save_buffer);"),
                        done.index("roster_reconcile(slot);"))
        reconcile = body(roster, "static void roster_reconcile(int slot)")
        self.assertLess(reconcile.index("arrival_save(slot, have_previous);"),
                        reconcile.index("Arrived with no Birth record or known arrival"))

    def test_a_birth_is_never_an_arrival(self):
        roster = (COD / "cod_roster.inc").read_text(encoding="utf-8")
        self.assertIn("arrival_noted_birth(cod_index_of((const unsigned char *)record));",
                      body(roster, "VvfpCauseNoteArrival(int game, const void *record)"))
        arrivals = (COD / "cod_arrivals.inc").read_text(encoding="utf-8")
        for site in ("0x42EF64u", "0x42EFD5u", "0x42F026u", "0x42F072u"):
            self.assertIn(site, arrivals)

    def test_the_custom_island_event_names_its_villagers(self):
        source = (ROOT / "native" / "vvfp_story_upgrades" / "story_custom.inc").read_text(encoding="utf-8")
        self.assertIn('arrived(game, index, "Custom Island Event");', source)
        spawn = source[source.index("int index = a->spawn(s);"):]
        self.assertLess(spawn.index("ce_tell_arrival(e->game, index);"), spawn.index("titles_set"))

    def test_start_over_deletes_the_marker(self):
        source = (SHARED / "save_reset.c").read_text(encoding="utf-8")
        self.assertIn('"%s\\\\Virtual Villagers Fun Patcher Data\\\\Arrivals\\\\Virtual Villagers " n '
                      '" Arrivals Recorded - Save %d.dat"', source)
        for game in "12345":
            self.assertIn(f'ARRIVALS_FORMAT("{game}")', source)
        cod = (COD / "vvfp_cause_of_death.c").read_text(encoding="utf-8")
        self.assertIn("arrival_reset(slot);", body(cod, "VvfpCauseVillageReset(int game, int slot)"))

    def test_the_marker_is_never_written_over_a_file_it_did_not_write(self):
        source = (SHARED / "arrival_backfill.h").read_text(encoding="utf-8")
        write = body(source, "static int vv_arrival_marker_write(int game, int slot)")
        self.assertIn("GetFileAttributesA(path) != INVALID_FILE_ATTRIBUTES", write)
        self.assertNotIn("MOVEFILE_REPLACE_EXISTING", write)


@unittest.skipUnless(CL.is_file(), "the 32-bit MSVC toolchain is not installed")
@unittest.skipUnless(TEST_DLL.is_file(), "test builds are not in the release source archive (tests/test_dlls)")
class ArrivedRecordHarness(unittest.TestCase):
    def test_the_harness_passes_in_all_five_games(self):
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(BUILD)],
            capture_output=True, text=True, timeout=600,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("== 0 failure(s) ==", result.stdout)
        for game in range(1, 6):
            self.assertIn(f"Virtual Villagers {game}\n", result.stdout)
        self.assertEqual(len(re.findall(r"^  ok ", result.stdout, re.M)), CHECKS, result.stdout)


if __name__ == "__main__":
    unittest.main()
