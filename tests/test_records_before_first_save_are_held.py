"""Records written before a village's first save are held, then filed under it.

The owner's first v1.35.27 tribes showed two defects from the same window:

  * VV1's and VV3's Births and Conceptions logs opened on "Conception 1" with
    no Village header -- the record created the file before any save had
    published the village, and the header is only ever written into an empty
    file, so the log never got one.
  * VV3's log held seven conceptions between fourteen villagers who are in
    neither of that tribe's saves. Only the two hooked callers reach VV3's
    conception routine, so they were live records of the villagers the game
    simulates before the player's tribe exists.

The parentage companion now holds such records until the village is known and
writes them then, dropping any whose villager no longer occupies its slot.
native/parentage_export/pending_harness.c drives the shipped DLL through that
window and checks the log on disk; against the v1.35.27 DLL it fails thirty-three of
its sixty-seven checks, and against v1.35.28's it fails twenty-two -- including
Epeli, the birth that DLL dropped in the owner's VV3 tribe -- which is what makes it a
regression test rather than a
restatement of the fix.

The harness needs the 32-bit MSVC toolchain, so it runs where that is installed
and is skipped elsewhere. The static checks below run everywhere.
"""
from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "native/parentage_export/parentage_export.c"
BUILD = ROOT / "scripts/build_pending_harness.ps1"
CL = Path(
    r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC"
    r"\14.51.36231\bin\Hostx64\x86\cl.exe"
)


def function(name: str) -> str:
    source = SOURCE.read_text(encoding="utf-8")
    start = re.search(r"^static (?:int|void) " + re.escape(name) + r"\(", source, re.M)
    assert start is not None, name
    return source[start.start():source.index("\n}", start.start())]


class RecordsBeforeFirstSaveAreHeld(unittest.TestCase):
    def test_both_writers_go_through_emit_record(self) -> None:
        source = SOURCE.read_text(encoding="utf-8")
        # The conception passes the table the game handed over; a birth has
        # none, and the tribe is then found where the game keeps it.
        self.assertIn("return emit_record(game_id, 0, records, text);", source)
        self.assertIn("return emit_record(game_id, 1, NULL, text);", source)

    def test_an_unknown_village_holds_rather_than_writes(self) -> None:
        emit = function("emit_record")
        known = emit.index("if (village[0] != '\\0' && saved_tribe_still_loaded(game_id)) {")
        publisher = emit.index("if (village[0] == '\\0' && !statistics_publisher_present()) {")
        held = emit.rindex("return hold_record(game_id, is_birth, records, text);")
        self.assertLess(known, publisher)
        self.assertLess(publisher, held,
                        "records must be held only when a publisher exists")
        self.assertIn("++pending_count;", function("hold_record"))

    def test_a_failed_write_keeps_the_record(self) -> None:
        """#449 review: a held record is released only once it is on disk."""
        flush = function("flush_pending")
        self.assertIn(
            "int outcome = append_record(g, village, entry->is_birth, entry->text);", flush)
        # Only a failure whose file was restored is retried: one that could not
        # be rolled back is released, because a retry could duplicate it.
        self.assertIn("if (outcome == APPEND_RETRY) {", flush)
        self.assertIn("stopped = 1;", flush)
        self.assertIn("pending[kept++] = *entry;", flush)
        emit = function("emit_record")
        self.assertIn("int outcome = append_record(g, village, is_birth, text);", emit)
        self.assertIn("if (outcome == APPEND_UNRECOVERABLE) {", emit)
        append = function("append_record")
        self.assertIn("if (!roll_back_append(path, original_size)) {", append)
        self.assertIn("return APPEND_UNRECOVERABLE;", append)
        self.assertIn("return APPEND_RETRY;", append)

    def test_the_first_save_writes_what_was_held(self) -> None:
        source = SOURCE.read_text(encoding="utf-8")
        ensure = source[source.index("static int ensure_parentage_log(\n    int game_id,"):]
        ensure = ensure[:ensure.index("\n}")]
        self.assertIn("flush_pending(game_id, village);", ensure)

    def test_the_whole_tribe_decides_whether_a_held_record_is_kept(self) -> None:
        """A held record is dropped only when its tribe's table was replaced.

        No single villager field is fixed for life -- the player renames
        villagers; island events, the Gong of Wonder and Origins upgrades
        de-age them; Change Appearance restyles them; likes change as they grow.
        v1.35.28 compared one villager's fields and dropped Epeli's birth in the
        owner's VV3 tribe. The owner chose a whole-tribe check instead."""
        flush = function("flush_pending")
        self.assertIn("!same_tribe(&held_tribes[entry->tribe], scratch_tribe)", flush)
        counts = function("still_counts")
        # A villager still counts on two of name, looks and own parents.
        self.assertIn("strcmp(then->name, now->name) == 0", counts)
        self.assertIn("then->head == now->head && then->body == now->body", counts)
        self.assertIn("strcmp(then->father_of, now->father_of) == 0", counts)
        self.assertIn("return same >= 2;", counts)
        self.assertNotIn("likes", counts)
        self.assertNotIn("age", counts)
        same = function("same_tribe")
        self.assertIn("return counted >= 1 && counted * 4 >= then->count;", same)
        # Pairs villagers by record slot: direct record access, never a scan.
        self.assertIn("then->member[i].slot", same)
        self.assertNotIn("find_record_by_name", same)

    def test_a_recalled_header_is_trusted_only_for_the_saved_tribe(self) -> None:
        """#449 review, P1: after Start Over the old tribe's header is still
        published, so a record may go straight under it only while the table
        still holds the tribe that was saved; otherwise it is held."""
        emit = function("emit_record")
        self.assertIn(
            "if (village[0] != '\\0' && saved_tribe_still_loaded(game_id)) {", emit)
        still = function("saved_tribe_still_loaded")
        self.assertIn("return same_tribe(saved_tribe, scratch_tribe);", still)
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn("int __stdcall EnsureParentageLogForVillage(", source)
        self.assertIn("remember_saved_tribe(game_id, (const unsigned char *)records);", source)
        population = (ROOT / "native/population_export/population_export.c").read_text(
            encoding="utf-8")
        self.assertIn('GetProcAddress(companion, "EnsureParentageLogForVillage")', population)
        self.assertIn("ensure_parentage_log_for_village(game_id, village, villagers);",
                      population)
        definition = (ROOT / "native/parentage_export/parentage_export.def").read_text(
            encoding="utf-8")
        self.assertIn("EnsureParentageLogForVillage=_EnsureParentageLogForVillage@12",
                      definition)

    def test_a_failed_append_is_rolled_back(self) -> None:
        """#449 review: a retried record must not leave a partial copy behind."""
        append = function("append_record")
        self.assertIn("original_size = log_file_size(path);", append)
        self.assertLess(append.index("original_size = log_file_size(path);"),
                        append.index('file = _wfopen(path, L"a");'))
        self.assertIn("if (!roll_back_append(path, original_size)) {", append)
        roll = function("roll_back_append")
        self.assertIn("SetEndOfFile(handle)", roll)

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
