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
window and checks the log on disk; against the v1.35.27 DLL it fails twenty-three of
its forty-three checks, which is what makes it a regression test rather than a
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
        self.assertIn("return emit_record(game_id, 0, mother, text);", source)
        self.assertIn("return emit_record(game_id, 1, rec, text);", source)

    def test_an_unknown_village_holds_rather_than_writes(self) -> None:
        emit = function("emit_record")
        known = emit.index("if (village[0] != '\\0' && saved_tribe_still_loaded(game_id)) {")
        publisher = emit.index("if (village[0] == '\\0' && !statistics_publisher_present()) {")
        held = emit.rindex("return hold_record(game_id, is_birth, subject, text);")
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

    def test_a_held_record_is_checked_against_its_own_slot(self) -> None:
        """Re-read by the pointer the game handed over -- never a scan."""
        check = function("still_the_same_villager")
        self.assertIn("memory_is_readable(entry->subject, g->stride)", check)
        self.assertIn("entry->subject + g->active) != 1", check)
        for field in ("name", "head", "body", "likes", "dislikes"):
            self.assertIn(f"entry->{field}", check)
        # The COMPLETE preference arrays, not the first rendered entry (#449
        # review), and an age that has not gone backwards.
        self.assertIn("memcmp(now.likes, entry->likes, sizeof(now.likes))", check)
        self.assertIn("memcmp(now.dislikes, entry->dislikes, sizeof(now.dislikes))", check)
        self.assertIn("now.age >= entry->age", check)
        self.assertNotIn("find_record_by_name", check)

    def test_a_recalled_header_is_trusted_only_for_the_saved_tribe(self) -> None:
        """#449 review, P1: after Start Over the old tribe's header is still
        published, so a record may go straight under it only while the table
        still holds the tribe that was saved; otherwise it is held."""
        emit = function("emit_record")
        self.assertIn(
            "if (village[0] != '\\0' && saved_tribe_still_loaded(game_id)) {", emit)
        still = function("saved_tribe_still_loaded")
        self.assertIn("still_the_same_villager(g, &saved_tribe[i].identity)", still)
        self.assertIn("return same * 2 > saved_count;", still)
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
