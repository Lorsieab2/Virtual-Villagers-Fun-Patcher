r"""The Village History log, and the folder every exported log now lives in.

THE HISTORY (#418). The live roster, "Village Population <n>.txt", is a
snapshot of who is alive now: rewritten every save, so a villager who dies is
absent from the next one. The owner wants a history as well, and chose
snapshot-per-save over matching villagers to their past selves: each save
appends a dated section to "Village History.txt" and nothing is ever decided
about whether two rows are the same person. Nothing can be mismatched because
nothing is matched.

THE FOLDERS. The owner's layout for every exported log:

    <save folder>\VVFP Logs\Tribe Population\        the roster
    <save folder>\VVFP Logs\Tribe History\           the history
    <save folder>\VVFP Logs\Tribe Parental Records\  the parentage log

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

POPULATION_DIR = 'L"VVFP Logs\\\\Tribe Population"'
HISTORY_DIR = 'L"VVFP Logs\\\\Tribe History"'
PARENTAL_DIR = 'L"VVFP Logs\\\\Tribe Parental Records"'


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
        self.assertIn('L"%ls\\\\Village History.txt"', path)

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
        for wide in ("VVFP Logs\\Tribe History", "Village History.txt",
                     "VVFP Logs\\Tribe Population"):
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
        self.assertNotIn("vv_save_folder_w(", path)

    def test_the_statistics_log_did_not_move(self):
        """Not named in the owner's layout; left exactly where it was."""
        paths = function(self.stat, "static int build_output_paths(")
        self.assertIn("vv_save_folder_w(", paths)
        self.assertNotIn("vv_save_subfolder_w(", paths)
        self.assertNotIn("VVFP Logs", self.stat)

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
        narrow_pop = '"VVFP Logs\\\\Tribe Population"'
        narrow_par = '"VVFP Logs\\\\Tribe Parental Records"'
        self.assertIn(narrow_pop, self.harness)
        self.assertIn(narrow_par, self.harness)
        self.assertIn('wsprintfA(pop1, "%s\\\\Village Population 1.txt", popdir);', self.harness)
        self.assertIn('wsprintfA(log1, "%s\\\\Virtual Villagers 1 Parentage Log 1.txt", pardir);',
                      self.harness)
        # statistics fixtures still sit in the save root
        self.assertIn('wsprintfA(stats1, "%s\\\\Village Statistics - Save 1.txt", folder);',
                      self.harness)

    def test_the_shipped_parentage_dll_carries_its_folder(self):
        self.assertIn("VVFP Logs\\Tribe Parental Records".encode("utf-16-le"),
                      PAR_DLL.read_bytes())


if __name__ == "__main__":
    unittest.main()
