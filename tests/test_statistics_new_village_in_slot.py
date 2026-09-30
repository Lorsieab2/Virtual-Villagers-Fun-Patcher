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

    def test_the_check_gates_the_flush(self):
        """Codex (PR #467): if moving the old files aside fails, the new
        village's events must not be flushed into the old village's files."""
        body = EXPORTER[EXPORTER.index("__declspec(dllexport) int __stdcall SaveVillageStatistics("):]
        body = body[:body.index("\n}\n")]
        self.assertRegex(body, r"if \(start_fresh_if_new_village\(game_id, save_id\)\) \{\s*vvs_flush\(&g_store\);")

    def test_old_files_are_moved_aside_never_deleted_or_overwritten(self):
        body = EXPORTER[EXPORTER.index("static int start_fresh_if_new_village("):]
        body = body[:body.index("\n}\n")]
        self.assertNotIn("DeleteFile", body)
        for moved in ("move_aside(g_store_counters, stamp)", "move_aside(g_store_stews, stamp)",
                      "move_aside(elders, stamp)"):
            self.assertIn(moved, body)
        self.assertIn("if (was > 0 && !shared) {", body)
        self.assertIn("return 0;                 /* keep the recorded roster: retry next save */", body)
        mover = EXPORTER[EXPORTER.index("static int move_aside("):]
        mover = mover[:mover.index("\n}\n")]
        self.assertIn("MoveFileExW(path, aside, 0)", mover)          # never replaces a file
        self.assertNotIn("MOVEFILE_REPLACE_EXISTING", mover)

    def test_renaming_never_looks_like_a_new_village(self):
        """Codex (PR #467): renaming every living villager must not discard
        the slot's tracking. Same slot AND (same name OR same fingerprint of
        likes, dislikes and parents' names)."""
        body = EXPORTER[EXPORTER.index("static int same_villager("):]
        body = body[:body.index("\n}\n")]
        self.assertIn("same fingerprint", body)
        self.assertIn("same name", body)
        self.assertIn("shared = same_villager(g_roster_was[i], g_roster_now[j]);", EXPORTER)


if __name__ == "__main__":
    unittest.main()
