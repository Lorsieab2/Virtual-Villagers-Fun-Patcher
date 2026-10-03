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
writes them then -- EVERY one of them. Each earlier attempt to drop some (a
villager no longer in its slot, then a tribe no longer matching) dropped real
records, because no villager field is fixed for life, and the owner ruled:
"no one should be dropped. nothing should be dropped."
native/parentage_export/pending_harness.c drives the shipped DLL through that
window and checks the log on disk. Records the tribe cannot vouch for (the
pre-tribe simulation's) are written with a closing Note line. Of its
ninety-three checks, v1.35.29's DLL fails nine (it adds no Note, though it
writes every record), the first labelling DLL five (a founders-only tribe,
renamed and restyled, was labelled -- Codex, #452), the whole-tribe DLL forty
(among them VV1's records once every founder is renamed and restyled),
v1.35.28's fifty-five (among them Epeli, the birth it dropped in the owner's
VV3 tribe) and v1.35.27's fifty-eight. That is what makes it a regression test
rather than a restatement of the fix.

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
        self.assertIn("return emit_record(game_id, KIND_BIRTH, NULL, text);", source)

    def test_an_unknown_village_holds_rather_than_writes(self) -> None:
        emit = function("emit_record")
        known = emit.index("if (village[0] != '\\0' && saved_tribe_still_loaded(game_id)) {")
        publisher = emit.index("if (village[0] == '\\0' && !statistics_publisher_present()) {")
        held = emit.rindex("return hold_record(game_id, kind, records, text);")
        self.assertLess(known, publisher)
        self.assertLess(publisher, held,
                        "records must be held only when a publisher exists")
        hold = function("hold_record")
        self.assertIn("++pending_count;", hold)
        # No cap: the queue grows rather than refusing a record.
        self.assertIn("realloc(", hold)
        self.assertNotIn("PENDING_MAX", SOURCE.read_text(encoding="utf-8"))

    def test_a_failed_write_keeps_the_record(self) -> None:
        """#449 review: a held record is released only once it is on disk."""
        flush = function("flush_pending")
        self.assertIn(
            "outcome = append_record(g, village, entry->kind, text);", flush)
        # Only a failure whose file was restored is retried: one that could not
        # be rolled back is released, because a retry could duplicate it.
        self.assertIn("if (outcome == APPEND_RETRY) {", flush)
        self.assertIn("stopped = 1;", flush)
        self.assertIn("pending[kept++] = *entry;", flush)
        emit = function("emit_record")
        self.assertIn("int outcome = append_record(g, village, kind, text);", emit)
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

    def test_no_held_record_is_ever_dropped(self) -> None:
        """The owner: "no one should be dropped. nothing should be dropped."

        Every held record is written at the next save; the only one released
        unwritten is a write whose partial output could not be rolled back,
        where a retry could only duplicate it."""
        flush = function("flush_pending")
        self.assertEqual(flush.count("release = 1;"), 1,
                         "a record is released only after append_record")
        self.assertLess(flush.index("append_record("), flush.index("release = 1;"))
        # The tribe comparison may only LABEL the record, never skip it.
        self.assertNotIn("continue", flush)
        self.assertEqual(flush.count("append_record("), 1)

    def test_a_record_the_tribe_cannot_vouch_for_is_labelled(self) -> None:
        """The owner asked for records from other villagers (the pre-tribe
        simulation, a tribe left unsaved by Start Over) to be told apart.

        The label uses the LOOSE rule -- one of name, looks or parents -- so
        renaming and restyling every founder cannot label the tribe's own
        records."""
        flush = function("flush_pending")
        self.assertIn(
            "!same_tribe(&held_tribes[entry->tribe], scratch_tribe, TRIBE_LOOSE)", flush)
        self.assertIn("labelled = label_record(entry->text);", flush)
        self.assertIn("outcome = append_record(g, village, entry->kind, text);", flush)
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn("#define TRIBE_LOOSE  1", source)
        self.assertIn("  Note: Recorded before this village was saved", source)
        # The note goes before the record's closing blank line.
        label = source[source.index("static char *label_record("):]
        self.assertIn("--body;", label[:label.index("\n}")])
        self.assertIn("entry->tribe = current_tribe_index(game_id, records);",
                      function("hold_record"))

    def test_preferences_recognise_renamed_and_restyled_founders(self) -> None:
        """Codex, #452 (P2): a tribe of founders only, all renamed and
        restyled before the first save, has no name, looks or parents left to
        match. The player cannot edit preferences, so the LOOSE rule -- the
        label's -- also counts an unchanged likes-and-dislikes fingerprint.
        Preferences change as villagers grow, so the STRICT rule ignores it."""
        counts = function("still_counts")
        self.assertIn("needed <= TRIBE_LOOSE && then->has_preferences", counts)
        self.assertIn("then->preferences == now->preferences", counts)
        take = function("take_tribe")
        self.assertIn("m->has_preferences = 1;", take)
        self.assertIn("value = -1;", take)

    def test_an_empty_parent_is_not_a_shared_parent(self) -> None:
        """copy_name_field renders an empty name as "(unnamed)", which made
        every founder "share parents" with every other founder and with the
        simulation's villagers. take_tribe reads the raw byte first."""
        take = function("take_tribe")
        self.assertIn("record[g->parent_father_name] != 0", take)
        self.assertIn("record[g->parent_mother_name] != 0", take)

    def test_a_recalled_header_is_trusted_only_for_the_saved_tribe(self) -> None:
        """#449 review, P1: after Start Over the old tribe's header is still
        published, so a record may go straight under it only while the table
        still holds the tribe that was saved; otherwise it is held."""
        emit = function("emit_record")
        self.assertIn(
            "if (village[0] != '\\0' && saved_tribe_still_loaded(game_id)) {", emit)
        still = function("saved_tribe_still_loaded")
        self.assertIn("return same_tribe(saved_tribe, scratch_tribe, TRIBE_STRICT);", still)
        # This decides only when and where a record is written. A wrong "not
        # the same" merely holds it to the next save; a wrong "the same" would
        # misfile it, so the stricter two-of-three rule stays.
        counts = function("still_counts")
        self.assertIn("return same >= needed;", counts)
        self.assertIn("#define TRIBE_STRICT 2", SOURCE.read_text(encoding="utf-8"))
        self.assertNotIn("likes", counts)
        self.assertIn("return counted >= 1 && counted * 4 >= then->count;",
                      function("same_tribe"))
        self.assertIn("then->member[i].slot", function("same_tribe"))
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
