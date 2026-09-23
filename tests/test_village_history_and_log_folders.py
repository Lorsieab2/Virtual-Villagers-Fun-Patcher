r"""The Village History log, and the folder every exported log now lives in.

THE HISTORY (#418). The live roster, "Village Population <n>.txt", is a
snapshot of who is alive now: rewritten every save, so a villager who dies is
absent from the next one. The owner wants a history as well, and chose
snapshot-per-save over matching villagers to their past selves: each save
appends a dated section to "Village History %d.txt" and nothing is ever decided
about whether two rows are the same person. Nothing can be mismatched because
nothing is matched.

THE FOLDERS. The owner's layout for every exported log:

    <save folder>\Virtual Villagers Fun Patcher Logs\Tribe Population\        the roster
    <save folder>\Virtual Villagers Fun Patcher Logs\Tribe History\           the history
    <save folder>\Virtual Villagers Fun Patcher Logs\Births and Conceptions\  the parentage log

The statistics log was not named and stays where it was. The reset must
delete from the same folders the exporters write to, so the literal strings
are pinned equal across the three files rather than merely present in each.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POP_C = ROOT / "native" / "population_export" / "population_export.c"
PAR_C = ROOT / "native" / "parentage_export" / "parentage_export.c"
STAT_C = ROOT / "native" / "statistics_export" / "statistics_export.c"
RESET_C = ROOT / "native" / "shared" / "save_reset.c"
RESET_H = ROOT / "native" / "shared" / "save_reset_harness.c"
FOLDER_H = ROOT / "native" / "shared" / "save_folder.h"
POP_DLL = ROOT / "assets" / "population" / "VVFP Population Export.dll"
PAR_DLL = ROOT / "assets" / "parentage" / "VVFP Parentage Export.dll"

POPULATION_DIR = 'L"Virtual Villagers Fun Patcher Logs\\\\Tribe Population"'
HISTORY_DIR = 'L"Virtual Villagers Fun Patcher Logs\\\\Tribe History"'
PARENTAL_DIR = 'L"Virtual Villagers Fun Patcher Logs\\\\Births and Conceptions"'
STATISTICS_DIR = 'L"Virtual Villagers Fun Patcher Logs\\\\Village Statistics"'


def function(source: str, opening: str) -> str:
    start = source.index(opening)
    end = source.index("\n}", start)
    return source[start:end]


class HistoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pop = POP_C.read_text(encoding="utf-8")
        self.history = function(self.pop, "static int append_history(")
        self.export = self.pop[self.pop.index("__stdcall WriteVillagePopulation("):]

    def test_the_history_is_appended_and_never_rewritten(self):
        """The roster is published by temporary-and-rename because it is a
        snapshot that must be atomically replaced. The history is the opposite:
        a log that must only ever grow."""
        self.assertIn('_wfopen(path, L"a")', self.history)
        self.assertNotIn('L"w"', self.history)
        self.assertNotIn("MoveFileExW", self.history)
        self.assertNotIn("DeleteFileW", self.history)

    def test_the_history_lives_in_its_own_folder(self):
        path = function(self.pop, "static int build_history_path(")
        self.assertIn("vv_save_subfolder_w(", path)
        self.assertIn(HISTORY_DIR, path)
        self.assertIn('L"%ls\\\\Village History %d.txt"', path)

    def test_the_export_appends_the_history_after_publishing_the_roster(self):
        """Order matters: a history failure must never cost the player the
        roster, so the roster is published first and the history's result is
        discarded."""
        call = "(void)append_history(g, villagers, game_id, village);"
        self.assertIn(call, self.export, "the history is not written at all")
        publish = self.export.index("publish_file(file, temporary, destination)")
        appended = self.export.index(call)
        sweep = self.export.index("Remove any roster files a LARGER village left behind")
        self.assertLess(publish, appended, "the history must follow the roster's publish")
        self.assertLess(appended, sweep, "the history must precede the stale-file sweep")
        # Discarded on purpose: no `if (!append_history` and no return on it.
        self.assertNotIn("if (!append_history", self.export)
        self.assertNotIn("if (append_history", self.export)

    def test_each_section_is_dated_and_headed_by_the_village(self):
        self.assertIn("GetLocalTime(&now)", self.history)
        self.assertIn("%04d-%02d-%02d %02d:%02d:%02d", self.history)
        self.assertIn("g->title", self.history)
        self.assertIn("village", self.history)

    def test_the_history_reuses_the_roster_writer(self):
        """One block format, maintained once: the same write_villager the
        roster uses, so the two files agree field for field."""
        self.assertIn("write_villager(file, g, record, written + 1, game_id, (int)index)",
                      self.history)

    def test_only_living_villagers_are_written_per_snapshot(self):
        """Each snapshot is who is alive AT THAT SAVE. Dead villagers are
        preserved by earlier snapshots, not by reading dead slots."""
        self.assertIn("if (*(const unsigned char *)(record + g->active) != 1) {",
                      self.history)

    def test_every_failure_path_closes_the_file(self):
        """An append that fails must not leak the handle; the next save must
        be able to open the file again.

        The `file == NULL` return is BEFORE the open succeeded and correctly
        closes nothing. From the first write onward, every `return 0` must be
        immediately preceded by fclose, and the success path closes too."""
        opened = self.history.index('_wfopen(path, L"a")')
        after_open = self.history[opened:]
        self.assertIn("if (file == NULL) {", after_open)
        # everything after the null check is on the open-succeeded path
        live = after_open[after_open.index("GetLocalTime(&now)"):]
        failing = live.count("return 0;")
        closed_then_failed = len(re.findall(r"fclose\(file\);\s*return 0;", live))
        self.assertGreaterEqual(failing, 3, "expected the header, villager and trailer writes to be checked")
        self.assertEqual(failing, closed_then_failed,
                         "a failure path after the open returns without closing the file")
        self.assertIn("return fclose(file) == 0;", live, "the success path must close and report it")

    def test_the_shipped_dll_carries_the_history(self):
        blob = POP_DLL.read_bytes()
        for wide in ("Virtual Villagers Fun Patcher Logs\\Tribe History", "Village History %d.txt",
                     "Virtual Villagers Fun Patcher Logs\\Tribe Population"):
            self.assertIn(wide.encode("utf-16-le"), blob, wide)


class LogFolderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pop = POP_C.read_text(encoding="utf-8")
        self.par = PAR_C.read_text(encoding="utf-8")
        self.stat = STAT_C.read_text(encoding="utf-8")
        self.reset = RESET_C.read_text(encoding="utf-8")
        self.harness = RESET_H.read_text(encoding="utf-8")

    def test_the_helper_is_declared(self):
        header = FOLDER_H.read_text(encoding="utf-8")
        self.assertIn("int vv_save_subfolder_w(wchar_t *out, const wchar_t *sub, int reserve);", header)
        self.assertIn("int vv_save_subfolder(char *out, const char *sub, int reserve);", header)

    def test_the_roster_moved(self):
        paths = function(self.pop, "static int build_log_paths(")
        self.assertIn("vv_save_subfolder_w(", paths)
        self.assertIn(POPULATION_DIR, paths)
        self.assertNotIn("vv_save_folder_w(", paths, "the roster no longer writes to the save root")

    def test_the_parentage_log_moved(self):
        path = function(self.par, "static int build_log_path(")
        self.assertIn("vv_save_subfolder_w(", path)
        self.assertIn(PARENTAL_DIR, path)
        # The log it RETURNS is always built from the subfolder, never from
        # the save root: the only vv_save_folder_w here resolves the retired
        # folder to migrate out of, and its result goes to `legacy_dir`.
        self.assertIn("destination,", path)
        self.assertNotIn("vv_save_folder_w(folder", path)

    def test_the_parentage_log_migrates_out_of_the_retired_folder(self):
        """A player upgrading from "VVFP Logs" keeps their existing logs. Left
        there, the next conception would start a fresh "Log 1.txt" in the new
        folder: the printed numbering would restart and one village's history
        would be split across two directories."""
        path = function(self.par, "static int build_log_path(")
        self.assertIn('VVFP Logs' + chr(92) * 2 + 'Births and Conceptions', path)
        # Moved, not copied: nothing is duplicated and an interrupted
        # migration cannot leave two copies of one record.
        self.assertIn("MoveFileW(from, to)", path)
        self.assertNotIn("CopyFile", path)
        # An existing file in the new folder is never overwritten.
        self.assertIn("already migrated: never overwrite", path)
        # The retired folder is probed, never created.
        self.assertNotIn('vv_save_subfolder_w(legacy_dir', path)

    def test_the_statistics_log_lives_in_its_own_folder(self):
        """The owner asked for every log the patcher writes to sit in its own
        folder under Virtual Villagers Fun Patcher Logs, statistics included, rather than loose in the
        save folder beside the .ldw files."""
        paths = function(self.stat, "static int build_output_paths(")
        self.assertIn("vv_save_subfolder_w(", paths)
        lit = re.search(r'vv_save_subfolder_w\(module_path, (L"[^"]+"), 64\)',
                        paths).group(1)
        self.assertEqual(lit, STATISTICS_DIR)

    def test_the_parentage_log_is_created_when_the_village_is(self):
        """The owner asked for the logs to exist as soon as a village does,
        not only once something happens in it -- which covers a brand-new
        village and one restarted with Start Over, since a reset deletes the
        previous village's files and the next save then finds none."""
        fn = function(self.par, "__declspec(dllexport) int __stdcall EnsureParentageLog(")
        # CREATE-IF-ABSENT, never a rewrite: the logs are append-only and a
        # record once written is never modified.
        self.assertIn('_wfopen(path, L"a")', fn)
        self.assertNotIn('L"w"', fn)
        # Only an EMPTY file gets the header, so an existing log is untouched.
        self.assertIn("ftell(file) == 0", fn)
        # A headerless file could not be attributed to any village, and Start
        # Over matches files to villages by that first line.
        self.assertIn("village[0] == " + chr(39) + chr(92) + "0" + chr(39), fn)

        # And the save path actually calls it, DLL to DLL.
        self.assertIn("ensure_parentage_log_for_village(game_id, village)", self.pop)
        self.assertIn('"VVFP Parentage Export.dll"', self.pop)
        self.assertIn('"EnsureParentageLog"', self.pop)
        # After the roster is published: a failure here must never cost the
        # player the file they actually rely on.
        self.assertLess(
            self.pop.index("publish_file(file, temporary, destination)"),
            self.pop.index("ensure_parentage_log_for_village(game_id, village)"))

    def test_the_log_migration_is_resumable(self):
        """Neither an absent source nor a failed move may end the walk.

        A move can fail transiently -- a lock, an antivirus scanner, a sharing
        violation. Stopping there left the later files behind, and because the
        earlier ones had already moved, the next attempt found file 1 absent
        and stopped immediately, treating "already migrated" as "end of run".
        Those files were stranded, and select_log_file then handed out a
        number an unmigrated file was still using: one village's history split
        across two folders with the same conception numbers in both."""
        path = function(self.par, "static int build_log_path(")
        body = path[path.index("for (moved = 1"):]
        # The walk must not break: every exit from an iteration is a continue.
        self.assertNotIn("break;", body)
        # An absent source is skipped, not terminal.
        self.assertIn("already migrated, or never existed", body)
        # A failed move is left for the next launch rather than ending the run.
        self.assertIn("retried on the next launch", body)
        # And it covers the same numbering range select_log_file walks.
        self.assertIn("moved <= 4096", body)
        # ...and it runs ONCE PER PROCESS, not once per record.
        # build_log_path runs for every conception and every birth, and
        # the walk no longer terminates early, so an ungated migration
        # would cost 4096 file checks per record written -- forever,
        # since the retired folder is never removed.
        self.assertIn("legacy_logs_migrated", path)
        self.assertIn("static int legacy_logs_migrated;", self.par)

    def test_the_history_rolls_instead_of_growing_forever(self):
        """The history appends a full roster on EVERY save, so without a roll
        it grows without bound -- about 27 KB per save on a real 85-villager
        village. It rolls on SIZE rather than record count because one
        snapshot is many lines."""
        path = function(self.pop, "static int build_history_path(")
        self.assertIn("HISTORY_BYTES_PER_FILE", path)
        self.assertIn("Village History %d.txt", path)
        # The threshold is a real bound, not a placeholder that never trips.
        m = re.search(r"HISTORY_BYTES_PER_FILE\s*=\s*([0-9*\s]+)\s*\}", self.pop)
        self.assertIsNotNone(m, "the threshold must be a compile-time constant")
        self.assertLessEqual(eval(m.group(1)), 64 * 1024 * 1024)
        self.assertGreater(eval(m.group(1)), 0)
        # A file that cannot be measured must keep the CURRENT file, never
        # roll: otherwise a failed stat scatters one village across new files.
        self.assertIn("return 0;", function(self.pop, "static long long history_file_size("))

    def test_the_reset_clears_statistics_from_both_locations(self):
        """A player who upgrades keeps the pre-move copy loose in the save
        folder. Clearing only the new path would leave a record of the village
        just erased sitting in a folder nothing writes to any more -- the same
        defect the parentage passes already guard against.

        Both must be addressed BY SLOT: a reset of slot 1 must not touch the
        other saves' statistics."""
        stat_lit = re.search(r'vv_save_subfolder_w\(module_path, (L"[^"]+"), 64\)',
                             function(self.stat, "static int build_output_paths(")).group(1)
        self.assertIn(stat_lit, self.reset)
        # The pre-move location is still swept, and neither sweep walks every
        # number: each formats the slot it was given.
        # Three locations now: the current folder, the same folder under the
        # pre-spell-out name, and the loose pre-move path. A player can be
        # upgrading from any of them, and a file left in a folder nothing
        # writes to any more would survive a reset meant to clear it.
        self.assertEqual(
            3, self.reset.count('Village Statistics - Save %d.txt'),
            "the reset must clear the current folder, the legacy folder "
            "name, AND the loose pre-move location")
        # The legacy folder name, spelled as C source: two backslashes.
        self.assertIn('VVFP Logs' + chr(92) * 2 + 'Village Statistics',
                      self.reset)
        self.assertNotIn('Village Statistics - Save *', self.reset)

    def test_the_reset_deletes_from_the_same_folders_the_exporters_write_to(self):
        """Pinned as EQUALITY of the literal, not mere presence: a reset that
        looks in a folder spelled one character differently deletes nothing
        and reports nothing wrong."""
        self.assertIn(POPULATION_DIR, self.reset)
        self.assertIn(PARENTAL_DIR, self.reset)
        # The exporters' literals, extracted, must be the reset's literals.
        pop_lit = re.search(r'vv_save_subfolder_w\(module_path, (L"[^"]+"), 64\)',
                            function(self.pop, "static int build_log_paths(")).group(1)
        par_lit = re.search(r'vv_save_subfolder_w\(folder, (L"[^"]+"), 64\)',
                            function(self.par, "static int build_log_path(")).group(1)
        self.assertEqual(pop_lit, POPULATION_DIR)
        self.assertEqual(par_lit, PARENTAL_DIR)
        self.assertIn(pop_lit, self.reset)
        self.assertIn(par_lit, self.reset)
        # And the history is NOT deleted by a reset: it is the permanent log.
        self.assertNotIn(HISTORY_DIR, self.reset)
        self.assertNotIn("Village History", self.reset)

    def test_the_reset_harness_creates_its_fixtures_where_the_exporters_write(self):
        narrow_pop = '"Virtual Villagers Fun Patcher Logs\\\\Tribe Population"'
        narrow_par = '"Virtual Villagers Fun Patcher Logs\\\\Births and Conceptions"'
        self.assertIn(narrow_pop, self.harness)
        self.assertIn(narrow_par, self.harness)
        self.assertIn('wsprintfA(pop1, "%s\\\\Village Population 1.txt", popdir);', self.harness)
        self.assertIn('wsprintfA(log1, "%s\\\\Virtual Villagers 1 Births and Conceptions Log 1.txt", pardir);',
                      self.harness)
        # statistics fixtures still sit in the save root
        self.assertIn('wsprintfA(stats1, "%s\\\\Village Statistics - Save 1.txt", folder);',
                      self.harness)

    def test_the_shipped_parentage_dll_carries_its_folder(self):
        self.assertIn("Virtual Villagers Fun Patcher Logs\\Births and Conceptions".encode("utf-16-le"),
                      PAR_DLL.read_bytes())


if __name__ == "__main__":
    unittest.main()
