"""A new village in the same save slot never inherits the old village's
statistics, stews or elders.

The statistics companion records each save's living roster and, when the next
save's living roster shares no villager with it (the owner's rule: a village
is identified by roster OVERLAP, never by name, since Start Over keeps the
tribe name), moves the slot's three .dat files aside before flushing. This
works whether or not the Start Over reset companion (shipped only with the
Origins and parentage features) is installed.

The roster is read with the Village Population exporter's measured layouts;
this pins that the two tables agree field for field, and that the check runs
before the flush that would otherwise add a new village's first events to the
old village's totals.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORTER = (ROOT / "native" / "statistics_export" / "statistics_export.c").read_text(encoding="utf-8")
POPULATION = (ROOT / "native" / "population_export" / "population_export.c").read_text(encoding="utf-8")


def _numbers(text: str) -> list[int]:
    return [int(v, 16) if v.lower().startswith("0x") else int(v) for v in re.findall(r"\b(0x[0-9A-Fa-f]+|\d+)u?\b", text)]


class NewVillageInSlotTests(unittest.TestCase):
    def test_roster_layouts_match_the_population_exporter(self):
        table = EXPORTER[EXPORTER.index("ROSTER_LAYOUTS[6] = {"):]
        table = re.sub(r"/\*.*?\*/", "", table[:table.index("};")], flags=re.S)
        rows = [_numbers(r) for r in re.findall(r"\{([^{}]*)\}", table)][1:]
        pop = POPULATION[POPULATION.index("GAME_LAYOUTS[6] = {"):]
        pop = re.sub(r"/\*.*?\*/", "", pop, flags=re.S)
        pop_rows = [_numbers(r) for r in re.findall(r"\{\s*1,([^{}]*)\}", pop)][:5]
        self.assertEqual(len(rows), 5)
        self.assertEqual(len(pop_rows), 5)
        for game, (mine, theirs) in enumerate(zip(rows, pop_rows), start=1):
            with self.subTest(game=game):
                # population: rva, is_pointer, record_base, stride, slots, active, age, head, body, name,
                # name_cap, 4 pregnancy-father fields, parent_father_name, parent_mother_name,
                # parent_name_cap, 4 parent appearance fields, skills, skill_count, float,
                # age_at_conception, litter, likes, dislikes, preference_slots
                rva, is_pointer, base, stride, slots, active, _age, _head, _body, name, cap = theirs[:11]
                pf_name, pm_name, p_cap = theirs[15:18]
                likes, dislikes, pref_slots = theirs[27:30]
                self.assertEqual(mine[:8], [rva, is_pointer, base, stride, slots, active, name, cap])
                # the rename-proof fingerprint fields
                self.assertEqual(mine[8:], [likes, dislikes, pref_slots, pf_name, pm_name, p_cap])

    def test_the_rollover_is_transactional_with_the_save(self):
        """Codex (PR #467, rounds 1-2): the decision is made before the save
        but nothing moves until the stock save succeeds; a save that detects a
        new village does not flush (its events stay in the save and are
        flushed into fresh files next time); the roster is committed after."""
        body = EXPORTER[EXPORTER.index("__declspec(dllexport) int __stdcall SaveVillageStatistics("):]
        body = body[:body.index("\n}\n")]
        decide = body.index("changed = village_changed(game_id, save_id);")
        flush = body.index("vvs_flush(&g_store);")
        write = body.index("result = ((save_writer)writer)(")
        commit = body.index("int committed = commit_roster(save_id, is_new, changed == ROSTER_DAMAGED);")
        self.assertLess(decide, flush)
        self.assertLess(flush, write)
        self.assertLess(write, commit)
        self.assertRegex(body, r"if \(changed == ROSTER_SAME\) \{\s*flushed = vvs_flush\(&g_store\);")
        self.assertRegex(body, r"if \(primary && \(result & 0xFF\) != 0 && changed != ROSTER_LOCKED\) \{")
        self.assertIn("int is_new = changed == ROSTER_NEW || changed == ROSTER_DAMAGED;", body)
        # Codex round 3: nothing is exported after a rollover that did not commit
        # (the first-load reconcile's flag is set around it: only the same
        # village's flushed save may raise a counter)
        self.assertRegex(body[commit:], r"if \(!is_new \|\| committed\) \{\s*g_rc_save_ok = changed == ROSTER_SAME "
                                        r"&& \(flushed & 1\) != 0;\s*WriteVillageStatistics\(")
        self.assertEqual(body.count("WriteVillageStatistics("), 1)
        check = EXPORTER[EXPORTER.index("static int village_changed("):]
        check = check[:check.index("\n}\n")]
        for writes in ("MoveFileExW", "DeleteFileW", "_wfopen_s(&f, temporary", '"w"'):
            self.assertNotIn(writes, check, "the pre-save decision must not change anything on disk")

    def test_old_files_are_moved_aside_never_deleted_or_overwritten(self):
        body = EXPORTER[EXPORTER.index("static int commit_roster("):]
        body = body[:body.index("\n}\n")]
        for moved in ("move_aside(g_store_counters, stamp)", "move_aside(g_store_stews, stamp)",
                      "move_aside(elders, stamp)"):
            self.assertIn(moved, body)
        self.assertIn("return 0;                 /* keep the recorded roster: retry next save */", body)
        # the roster replacement is checked, and only the roster's own temp file is ever deleted
        self.assertIn("if (!MoveFileExW(temporary, roster, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {", body)
        self.assertEqual(set(__import__("re").findall(r"DeleteFileW\((\w+)\)", body)), {"temporary"})
        mover = EXPORTER[EXPORTER.index("static int move_aside("):]
        mover = mover[:mover.index("\n}\n")]
        self.assertIn("MoveFileExW(path, aside, 0)", mover)          # never replaces a file
        self.assertNotIn("MOVEFILE_REPLACE_EXISTING", mover)

    def test_elders_are_recorded_even_if_the_log_cannot_be_opened(self):
        """Codex (PR #467, round 2): the elder .dat is updated on every
        successful save before the text log is opened."""
        body = EXPORTER[EXPORTER.index("__declspec(dllexport) int __stdcall WriteVillageStatistics("):]
        body = body[:body.index("\n}\n")]
        update = body.index("g_elders_ready = 0;")
        # The log is opened by write_statistics_file, called after the update.
        opened = body.index("write_statistics_file(game_id, manager, save_id, village)")
        self.assertLess(update, opened)
        self.assertIn("vv1_village_elders(manager);", body[update:opened])
        self.assertIn("village_elders_for(game_id);", body[update:opened])

    # Which rosters are the same village (renames, a lone coincidental name,
    # a tiny village's birth and death) is tested against the real C in
    # tests/test_roster_match.py.

    def test_an_unreadable_roster_is_never_the_same_village(self):
        """Codex (PR #467, round 3): only a MISSING roster is a first run. A
        locked roster skips flush, commit and log; a damaged one is a new
        village whose roster is moved aside, never overwritten."""
        check = EXPORTER[EXPORTER.index("static int village_changed("):]
        check = check[:check.index("\n}\n")]
        self.assertRegex(check, r"GetFileAttributesW\(roster\) == INVALID_FILE_ATTRIBUTES\) \{\s*return ROSTER_SAME;")
        self.assertRegex(check, r'_wfopen_s\(&f, roster, L"rb"\) != 0 \|\| f == NULL\) \{\s*return ROSTER_LOCKED;')
        self.assertRegex(check, r'"VVFP VILLAGE ROSTER v1", 22\) != 0\) \{\s*fclose\(f\);\s*return ROSTER_DAMAGED;')
        self.assertRegex(check, r"if \(tabs != 2\) \{[^}]*return ROSTER_DAMAGED;")
        commit = EXPORTER[EXPORTER.index("static int commit_roster("):]
        commit = commit[:commit.index("\n}\n")]
        self.assertRegex(commit, r"if \(ok && damaged\) \{\s*ok = move_aside\(roster, stamp\);")
        self.assertLess(commit.index("move_aside(elders, stamp)"), commit.index("move_aside(roster, stamp)"))


if __name__ == "__main__":
    unittest.main()
