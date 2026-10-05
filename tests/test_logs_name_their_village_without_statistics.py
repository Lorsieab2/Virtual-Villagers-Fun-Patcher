"""Cause of Death names the village for the logs, with or without Statistics.

Codex (#504 review): with Cause of Death and Write Births and Conceptions Log
ticked but Village Statistics not, emit_record() had no published village, so
the Deaths and Unaccounted Villagers records were appended at once with an
empty header. Such files are attributed to every village, so later villages
appended to the same history, Start Over could not identify and delete the
erased village's records, and the logs were not created at the first save as
Cause of Death's own description promises.

The statistics companion is not the only DLL on the game's save call: Cause
of Death's own hook sits right after it (the roster reconciliation). It now
hands the parentage DLL the save buffer and slot there
(PublishVillageAtSave), which publishes the header the statistics companion
would have -- the same name read, the same format -- and creates the logs, so
the logs are correct without forcing Village Statistics on. All five games
share the same code and the same log format.

native/parentage_export/village_publisher_harness.c drives the shipped DLL
through it in all five games' record geometry; against the DLL before this
fix it fails (the records are written at once, unheaded). The static checks
below pin the wiring on both sides.
"""
from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARENTAGE = ROOT / "native/parentage_export/parentage_export.c"
CAUSE = ROOT / "native/vvfp_cause_of_death"
BUILD = ROOT / "scripts/build_village_publisher_harness.ps1"
CL = Path(
    r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC"
    r"\14.51.36231\bin\Hostx64\x86\cl.exe"
)


def function(source: str, name: str) -> str:
    start = re.search(r"^(?:static |__declspec\(dllexport\) )[^\n]*\b" + re.escape(name) + r"\(",
                      source, re.M)
    assert start is not None, name
    return source[start.start():source.index("\n}", start.start())]


class LogsNameTheirVillageWithoutStatistics(unittest.TestCase):
    def test_a_village_is_held_for_when_either_companion_will_name_it(self) -> None:
        source = PARENTAGE.read_text(encoding="utf-8")
        emit = function(source, "emit_record")
        self.assertIn("if (village[0] == '\\0' && !village_publisher_present(game_id)) {", emit)
        self.assertNotIn("statistics_publisher_present()", emit)
        present = function(source, "village_publisher_present")
        self.assertIn("return statistics_publisher_present() || cause_of_death_publishes(game_id);", present)
        cause = function(source, "cause_of_death_publishes")
        # Not loaded yet: this DLL loads it rather than assume it will load
        # (#512 review) -- a file that cannot load, or lacks the exports,
        # will never name a village, which is final like a refusal. It is
        # the already-loaded module, else loaded by its full path in the
        # patcher's folder (native/shared/patcher_files.h), never by a bare
        # name from the DLL search order.
        self.assertIn('module = vvfp_patcher_dll("VVFP Cause of Death.dll");', cause)
        self.assertNotIn("LoadLibrary", cause)
        self.assertIn('|| GetProcAddress(module, "VvfpCauseInstall") == NULL) {\n            cause_state = -1;', cause)
        self.assertIn('GetProcAddress(module, "VvfpCauseNamesVillage")', cause)
        self.assertIn("if (state == -1) {\n        cause_state = -1;", cause)
        # Not installed yet: its save hook is armed so a save before the
        # install still names the village (#512 review, The Secret City);
        # a hook that cannot be armed is final.
        self.assertIn("if (state == 0 && game_id >= GAME_VV1 && game_id <= GAME_VV5 && !arm_save(game_id)) {", cause)

    def test_with_no_publisher_held_records_go_first(self) -> None:
        emit = function(PARENTAGE.read_text(encoding="utf-8"), "emit_record")
        branch = emit[emit.index("!village_publisher_present(game_id)"):]
        self.assertLess(branch.index("flush_pending(game_id, village);"),
                        branch.index("return append_record(g, village, kind, text) == APPEND_WRITTEN;"))

    def test_the_save_publishes_exactly_what_statistics_would(self) -> None:
        source = PARENTAGE.read_text(encoding="utf-8")
        publish = function(source, "PublishVillageAtSave")
        self.assertIn("if (statistics_publisher_present()) {\n        return 0;", publish)
        self.assertIn("vv_village_name(game_id, (const unsigned char *)save_buffer - 8, name)", publish)
        self.assertIn("vv_village_header(header, sizeof header, name, slot)", publish)
        self.assertIn("vv_village_publish(header);", publish)
        self.assertIn("return ensure_parentage_log(game_id, header, villager_table(game_id));", publish)
        # The statistics companion's own sequence, for comparison.
        stats = (ROOT / "native/statistics_export/statistics_export.c").read_text(encoding="utf-8")
        self.assertIn("vv_village_name(game_id, manager, village_name)", stats)
        self.assertIn("vv_village_header(\n            village, sizeof village, village_name, save_id)", stats)
        self.assertIn(
            "PublishVillageAtSave=_PublishVillageAtSave@12",
            (ROOT / "native/parentage_export/parentage_export.def").read_text(encoding="utf-8"),
        )

    def test_cause_of_death_names_the_village_before_it_reconciles(self) -> None:
        roster = (CAUSE / "cod_roster.inc").read_text(encoding="utf-8")
        for name, buffer in (
            ("roster_saved", "cod_save_done(slot, (const void *)(uintptr_t)(regs[R_ESI] + 8u));"),
            ("vv1_written", "cod_save_done(slot, (const void *)(uintptr_t)reg_stack(regs, 0x210));"),
        ):
            with self.subTest(hook=name):
                self.assertIn(buffer, function(roster, name))
        done = function(roster, "cod_save_done")
        self.assertLess(done.index("cod_publish_village(save_buffer, slot);"),
                        done.index("roster_reconcile(slot);"))
        cause = (CAUSE / "vvfp_cause_of_death.c").read_text(encoding="utf-8")
        publish = function(cause, "cod_publish_village")
        self.assertIn("(void)publish_village(g_game, save_buffer, slot);", publish)
        self.assertIn('GetProcAddress(module, "PublishVillageAtSave")', cause)
        self.assertIn("return install_state;", function(cause, "VvfpCauseNamesVillage"))
        for definition in ("vvfp_cause_of_death.def", "vvfp_cause_of_death_test.def"):
            with self.subTest(definition=definition):
                self.assertIn("VvfpCauseNamesVillage=_VvfpCauseNamesVillage@0",
                              (CAUSE / definition).read_text(encoding="utf-8"))

    def test_a_refused_install_releases_what_was_held_for_it(self) -> None:
        """Codex (#512 review): records held for Cause of Death were written
        only when a later record noticed it had been refused -- with none,
        they were lost at exit. The refusal itself now releases them."""
        cause = (CAUSE / "vvfp_cause_of_death.c").read_text(encoding="utf-8")
        install = function(cause, "VvfpCauseInstall")
        self.assertIn("} else if (cod_log_ready() && release_held != NULL) {", install)
        self.assertIn("(void)release_held(game);", install)
        self.assertIn('GetProcAddress(module, "ReleaseHeldRecords")', cause)
        parentage = PARENTAGE.read_text(encoding="utf-8")
        release = function(parentage, "ReleaseHeldRecords")
        self.assertIn("if (village_publisher_present(game_id)) {\n        return 0;", release)
        self.assertIn('flush_pending(game_id, "");', release)
        self.assertIn(
            "ReleaseHeldRecords=_ReleaseHeldRecords@4",
            (ROOT / "native/parentage_export/parentage_export.def").read_text(encoding="utf-8"),
        )

    def test_a_save_before_the_install_names_the_village(self) -> None:
        cause = (CAUSE / "vvfp_cause_of_death.c").read_text(encoding="utf-8")
        arm = function(cause, "VvfpCauseArmSave")
        self.assertIn("roster_save_site();", arm)
        self.assertIn("if (cod_install_sites(0)) {", arm)
        install = function(cause, "VvfpCauseInstall")
        # The armed hook stays sites[0]; the install adds the rest after it.
        self.assertIn("site_count = save_armed ? 1 : 0;", install)
        self.assertIn("if (!save_armed) {\n        roster_save_site();", install)
        self.assertIn("if (cod_install_sites(save_armed ? 1 : 0)) {", install)
        roster = (CAUSE / "cod_roster.inc").read_text(encoding="utf-8")
        done = function(roster, "cod_save_done")
        self.assertIn("cod_publish_village(save_buffer, slot);", done)
        # Only once installed: the graves the Deaths log lacks (after the
        # player's Repair; cod_backfill.inc), then the reconciliation.
        installed = done[done.index("if (install_state == 1) {"):]
        self.assertLess(installed.index("backfill_at_save(slot, save_buffer);"),
                        installed.index("roster_reconcile(slot);"))
        for name in ("roster_saved", "vv1_written"):
            self.assertIn("cod_save_done(slot, ", function(roster, name))
        for definition in ("vvfp_cause_of_death.def", "vvfp_cause_of_death_test.def"):
            self.assertIn("VvfpCauseArmSave=_VvfpCauseArmSave@4", (CAUSE / definition).read_text(encoding="utf-8"))

    def test_the_shipped_dlls_carry_the_new_exports(self) -> None:
        import sys
        sys.path.insert(0, str(ROOT / "src"))
        from vv_fun_patcher import _pe_export_names
        parentage = (ROOT / "assets/parentage/VVFP Parentage Export.dll").read_bytes()
        cause = (ROOT / "assets/cause_of_death/VVFP Cause of Death.dll").read_bytes()
        self.assertIn(b"PublishVillageAtSave", _pe_export_names(parentage))
        self.assertIn(b"ReleaseHeldRecords", _pe_export_names(parentage))
        self.assertIn(b"VvfpCauseNamesVillage", _pe_export_names(cause))
        self.assertIn(b"VvfpCauseArmSave", _pe_export_names(cause))

    @unittest.skipUnless(CL.is_file(), "the 32-bit MSVC toolchain is not installed")
    def test_the_harness_passes_against_the_shipped_dll(self) -> None:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(BUILD)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("== 0 failure(s) ==", result.stdout)


if __name__ == "__main__":
    unittest.main()
