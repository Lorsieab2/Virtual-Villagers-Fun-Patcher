"""Custom titles (Story / Cheat Upgrades, Custom Island Event) persist per save slot.

The owner: a custom title is "persisted per save slot in a patcher .dat file
beside the saves", untracked data goes in a .dat file (never in spare record
bytes), the folder name spells out "Virtual Villagers Fun Patcher", and "the
.dat follows the Start Over reset".

native/vvfp_story_upgrades/custom_titles_harness.c compiles the companion's
own title store (story_titles.inc) and the reset (native/shared/save_reset.c)
unchanged and runs them against real files in a fresh %TEMP% folder (never
Documents\\LDW): publish, the documented format, a new session reading it
back, one file per slot, a reused record never inheriting a title, a dead
villager's title dropped, an invalid file set aside, and Start Over deleting
the slot's file in all five games without the table writing it back.  It
needs the 32-bit MSVC toolchain and is skipped elsewhere; the static checks
below hold the pieces in place.
"""
from __future__ import annotations

import re
import struct
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "scripts" / "build_custom_titles_harness.ps1"
HARNESS = ROOT / "native" / "vvfp_story_upgrades" / "custom_titles_harness.c"
FORMAT = ROOT / "native" / "shared" / "custom_titles.h"
RESET = ROOT / "native" / "shared" / "save_reset.c"
STORE = ROOT / "native" / "vvfp_story_upgrades" / "story_titles.inc"
CL = Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC"
          r"\14.51.36231\bin\Hostx64\x86\cl.exe")


class CustomTitlesFile(unittest.TestCase):
    def test_the_file_lives_in_the_spelled_out_data_folder(self):
        text = FORMAT.read_text(encoding="utf-8")
        self.assertIn('#define VV_TITLES_SUBFOLDER "Virtual Villagers Fun Patcher Data\\\\Custom Titles"', text)
        self.assertIn('"\\\\Custom Titles - Save 0.dat"', text)
        self.assertNotIn("VVFP", re.sub(r"/\*.*?\*/", "", text, flags=re.S))

    def test_start_over_deletes_it_in_every_game(self):
        text = RESET.read_text(encoding="utf-8")
        self.assertIn('"%s\\\\Virtual Villagers Fun Patcher Data\\\\Custom Titles\\\\Custom Titles - Save %d.dat"',
                      text)
        table = text[text.index("SIDECAR_FORMATS[5][SIDECAR_FORMAT_COUNT]"):]
        table = table[:table.index("};")]
        self.assertEqual(table.count("CUSTOM_TITLES_FORMAT"), 5)
        self.assertIn("for (i = 0; i < SIDECAR_FORMAT_COUNT; ++i)", text)

    def test_start_over_forgets_the_table_before_any_freeze(self):
        """Review of #585 (v1.35.71): Start Over's founders share nobody with the last look, like the title
        screen's other array; the table froze before noticing the deleted file and kept the erased
        village's titles.  The file is looked at before a freeze and while frozen, and the reset's own
        call forgets the slot's table at once (harness: START OVER TO A FOUNDER ROSTER...)."""
        text = STORE.read_text(encoding="utf-8")
        tick = text[text.index("static void titles_pass(int game, int sweep) {"):]
        self.assertLess(tick.index("if (titles_reset_detected()) {\n            return;"),
                        tick.index("if (foreign && !titles.frozen) {\n        titles.frozen = 1;"))
        story = (ROOT / "native" / "vvfp_story_upgrades" / "vvfp_story_upgrades.c").read_text(encoding="utf-8")
        reset = story[story.index("void __stdcall VvfpStoryVillageReset(int game, int slot) {"):]
        self.assertIn("titles_village_reset(game, slot);", reset[:reset.index("\n}\n")])
        harness = HARNESS.read_text(encoding="utf-8")
        self.assertIn("START OVER TO A FOUNDER ROSTER FORGETS THE OLD TITLES (game %d)", harness)
        self.assertIn("VvfpStoryVillageReset forgets the slot's titles at once (game %d)", harness)

    def test_the_store_uses_the_shared_durable_sidecar_helpers(self):
        text = STORE.read_text(encoding="utf-8")
        for needle in ("vv_sidecar_load(", "vv_sidecar_publish(", "vv_titles_validate",
                       "titles_reset_detected()"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)

    def test_the_harness_covers_every_case(self):
        text = HARNESS.read_text(encoding="utf-8")
        for case in (
            "CUSTOM TITLES FILE PUBLISHED BESIDE THE SAVES",
            "A NEW SESSION READS THE TITLE BACK FROM THE .DAT",
            "A REUSED RECORD NEVER INHERITS THE TITLE",
            "A VILLAGER WHO DIES LOSES THE TITLE",
            "THE INVALID FILE IS MOVED ASIDE, NOT OVERWRITTEN",
            "START OVER DELETES SLOT 1'S TITLES (game %d)",
            "THE OLD VILLAGE'S TITLES ARE FORGOTTEN AFTER START OVER",
            "THE DELETED FILE IS NOT WRITTEN BACK",
            "AFTER AN UNTICKED START OVER ONLY THE NEW TITLE IS WRITTEN",
            "A FAILED WRITE LEAVES THE CHANGED TITLE AS IT WAS IN MEMORY",
            "A FAILED WRITE ADDS NO TITLE IN MEMORY",
            "A FAILED WRITE REMOVES NO TITLE IN MEMORY",
            "AFTER A RELOAD KAI [1 -> 0] KEEPS HIS TITLE",
            "THE FOLLOWED TITLES ARE WRITTEN BACK: a new session reads them at their new records",
            "A VILLAGER WHO MOVED IN THIS SESSION IS NOT SWEPT AWAY AS DEAD",
            "... and the dead Hina's title waits PENDING, shown on nobody: a load never drops a title",
            # v1.35.70 (the owner): a title is never dropped because its villager is ambiguous.
            "AN IDENTICAL-LOOKING NAMESAKE AFTER A RELOAD: THE TITLE IS KEPT PENDING, SHOWN ON NEITHER",
            "... the entry is kept, pending -- never dropped",
            "THE FILE STILL HOLDS THE PENDING TITLE, WITH THE WHOLE IDENTITY IT WAS KEPT BY",
            "TWO COULD BE HIM AT ONCE: THE PENDING TITLE IS MARKED CONTESTED IN THE FILE",
            # The owner (v1.35.70): when the others die or leave, the one left is never taken for them.
            "THE NAMESAKE DIES: THE ONE KAI LEFT IS NOT GIVEN THE CONTESTED TITLE -- IT WAITS FOR THE PLAYER",
            "... NOR AFTER A RELOAD WITH ONE KAI LEFT: STILL PENDING AND CONTESTED",
            "THE NAMESAKE'S LIKES CHANGE: THE CONTESTED TITLE STILL WAITS, GIVEN TO NEITHER",
            "A NEVER-CONTESTED PENDING TITLE BINDS AGAIN WHEN EXACTLY ONE VILLAGER HAS THE WHOLE IDENTITY",
            # The owner (v1.35.70): a load is never a death; a corrupted-skill reset is not a lower skill.
            "A TITLE WHOSE VILLAGER WAS RENAMED AND THEN RELOADED WITHOUT A SAVE WAITS PENDING, NEVER DROPPED",
            "THE STORED SKILL IS THE ONE THE CORRUPTED-SKILL RESET LEAVES (100)",
            "A CORRUPTED SKILL RESET (150 -> 100) DOES NOT STOP THE TITLE FOLLOWING ITS VILLAGER",
            "A CORRUPTED SKILL RESET (-7 -> 0) DOES NOT STOP THE TITLE FOLLOWING ITS VILLAGER",
            "THE TITLED KAI GONE, A YOUNGER NAMESAKE IS NOT GIVEN THE TITLE: IT STAYS PENDING",
            "... nor a namesake with a lower skill",
            "... nor a namesake of the other sex",
            "TWINS IDENTICAL IN EVERYTHING: THE TITLE STAYS PENDING, SHOWN ON NEITHER, KEPT",
            "... and the file keeps it pending for the reconciliation to ask about",
            "a surviving Kai is not given either Kai's title",
            "... both entries wait pending, and the file still loads (no record listed twice)",
            "A YOUNGER NAMESAKE PACKED INTO THE TITLE'S OLD RECORD IS NOT GIVEN IT: THE TITLE FOLLOWS ITS VILLAGER",
            "AT THE CAP A TITLED VILLAGER MOVED BY LOAD PACKING KEEPS HER TITLE (Ana [6 -> 5])",
            "A BIRTH INTO A FREED RECORD AT THE CAP NEVER INHERITS THE TITLE (Hoku's waits, pending)",
            "A BIRTH INTO A DEAD VILLAGER'S RECORD AT THE CAP NEVER INHERITS THE TITLE (in session: she died)",
            "AN OLD-FORMAT (VERSION 2) FILE STILL LOADS AND FOLLOWS",
            "... and is written back as version 3, with the villager's looks",
            "A PURE MOVE IS WRITTEN BACK: the next session finds Kai's title at record 0",
            "with nothing moved, the twin's title is kept on the record it was set on",
            "... and shown there, on that twin only",
            "another villager's rename is not a move: the twin's title stays",
            "a namesake born in the same session does not inherit the title",
            "... and the title is shown again when its villager is back",
            "a lookup before any tick follows the table first: the twin's title is kept pending, not shown",
            "a slot switched back to is followed afresh: the twin's title is not shown on the old look",
            "another villager in the record is not shown the title",
            "the first lookup's follow does not sweep: the title is still there for its villager",
            "A RENAMED VILLAGER KEEPS THE TITLE",
            "... and the file has it under the new name",
            "a different villager in the record is not a rename: not shown on them, and -- nobody saw Kainoa die -- the title waits pending",
            # v1.35.68: an island event changed Alapai's dislikes ("Custom title: Moon Mother -> none").
            "THE TITLE SURVIVES A LIKES / DISLIKES CHANGE, ASKED IN THE SAME FRAME (game %d)",
            "... and every tick after it (game %d)",
            "... and the file has it under the new identity (game %d)",
            "an event changing everyone's likes keeps every title (game %d)",
            "a newborn namesake in the freed record does not get the title (game %d)",
            "A PACKED RELOAD NEVER GIVES THE DEAD TWIN'S TITLE TO HER NAMESAKE (game %d)",
            "A VILLAGE OF ONE KEEPS THE TITLE THROUGH A LIKES CHANGE (game %d)",
        ):
            with self.subTest(case=case):
                self.assertIn(case, text)

    @unittest.skipUnless(CL.exists(), "the 32-bit MSVC toolchain is not installed")
    def test_the_harness_passes_on_real_files(self):
        run = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(BUILD)],
            capture_output=True, text=True, timeout=600)
        self.assertEqual(run.returncode, 0, run.stdout[-3000:] + run.stderr[-2000:])
        self.assertIn("0 failure(s)", run.stdout)
        self.assertNotIn("[FAIL]", run.stdout)
        for game in range(1, 6):
            with self.subTest(game=game):
                self.assertIn(f"[PASS] THE TITLE SURVIVES A LIKES / DISLIKES CHANGE, ASKED IN THE SAME FRAME "
                              f"(game {game})", run.stdout)

    def test_an_ambiguous_title_is_kept_pending_never_dropped(self):
        """v1.35.70, the owner: a title is never dropped because its villager became ambiguous after
        a reload; it is kept pending (shown on nobody) and bound again only by the whole identity."""
        store = STORE.read_text(encoding="utf-8")
        fmt = FORMAT.read_text(encoding="utf-8")
        self.assertNotIn("AMBIGUOUS AFTER A RELOAD IS DROPPED", store)
        self.assertIn("AMBIGUOUS IS PENDING, NEVER DROPPED", store)
        self.assertIn("#define VV_TITLE_PENDING 0xFFFFFFFFu", fmt)
        self.assertIn("#define VV_TITLES_VERSION 3u", fmt)
        self.assertIn("vv_title_looks_could_be(&e->looks, &now, story_title_skills_float(game))", store)

    def test_every_store_kept_by_the_title_identity_follows_a_likes_change(self):
        """v1.35.68: the custom titles (Story Upgrades) and New Believers' Former Heathens (Cause of
        Death) are both kept by vv_title_identity (name, likes, dislikes); both carry their entries to
        the new identity when an event changes a villager's likes or dislikes in place."""
        titles = (ROOT / "native" / "vvfp_story_upgrades" / "story_titles.inc").read_text(encoding="utf-8")
        self.assertIn("vv_roster_changed_in_place(TITLES_ROSTER", titles)
        self.assertIn("titles_relook(game);\n        i = titles_find((unsigned int)index);", titles,
                      "the lookup the Island Events log makes in the same frame re-looks first")
        former = (ROOT / "native" / "vvfp_cause_of_death" / "cod_former.inc").read_text(encoding="utf-8")
        self.assertIn("vv_roster_changed_in_place(n, former_roster", former)
        self.assertIn("former_rekey(former_roster[renamed], now[renamed])", former)
        arrivals = (ROOT / "native" / "vvfp_cause_of_death" / "cod_arrivals.inc").read_text(encoding="utf-8")
        self.assertIn("former_follow(records);", arrivals)


class ThePatchersOwnReader(unittest.TestCase):
    """src/vv_titles_file.py reads exactly what the companion's vv_titles_validate accepts."""

    def setUp(self):
        import sys
        sys.path.insert(0, str(ROOT / "src"))
        import vv_titles_file
        self.tf = vv_titles_file

    def test_version_3_round_trips_with_pending_entries(self):
        tf = self.tf
        entries = [tf.Entry(4, 77, "Helpful Spirit", True, 500, 3, 4, 1, (20, 21, 22, 23, 24, 0)),
                   tf.Entry(tf.PENDING, 78, "Moon Mother", True, 300, 1, 2, 2, (5,) * 5 + (0,)),
                   tf.Entry(tf.PENDING, 78, "Twin Title", False)]
        data = tf.serialise(3, entries)
        self.assertEqual(len(data), 16 + 3 * 84)
        version, back = tf.read(data, 3)
        self.assertEqual(version, 3)
        self.assertEqual(back, entries)
        self.assertEqual([e.pending for e in back], [False, True, True])
        self.assertIsNone(tf.read(data, 2))                       # another game's file

    def test_version_2_still_reads(self):
        tf = self.tf
        data = b"VCT1" + struct.pack("<III", 2, 1, 1) + struct.pack("<II", 4, 77) + b"Helpful Spirit".ljust(32, b"\0")
        self.assertEqual(tf.read(data, 1), (2, [tf.Entry(4, 77, "Helpful Spirit")]))

    def test_what_the_companion_sets_aside_is_not_read(self):
        tf = self.tf
        good = tf.serialise(1, [tf.Entry(1, 9, "A", True, 1, 1, 1, 1)])
        bad_flags = bytearray(good)
        bad_flags[24] = 2
        unknown_with_looks = bytearray(tf.serialise(1, [tf.Entry(1, 9, "A")]))
        unknown_with_looks[30] = 1
        twice = tf.serialise(1, [tf.Entry(1, 9, "A"), tf.Entry(1, 10, "B")])
        pending_twice = tf.serialise(1, [tf.Entry(tf.PENDING, 9, "A"), tf.Entry(tf.PENDING, 10, "B")])
        v2_pending = b"VCT1" + struct.pack("<III", 2, 1, 1) + struct.pack("<II", tf.PENDING, 9) + b"A".ljust(32, b"\0")
        self.assertIsNotNone(tf.read(good, 1))
        self.assertIsNotNone(tf.read(pending_twice, 1))           # pending entries hold no record
        for data in (bytes(bad_flags), bytes(unknown_with_looks), twice, v2_pending, good[:-1],
                     b"VCT1" + struct.pack("<III", 1, 1, 0)):
            self.assertIsNone(tf.read(data, 1))

    def test_the_whole_identity_rule(self):
        tf = self.tf
        e = tf.Entry(tf.PENDING, 9, "A", True, 500, 3, 4, 1, (20,) * 5 + (0,))
        same = dict(age=500, head=3, body=4, sex=1, skills=(20,) * 5 + (0,))
        self.assertTrue(tf.could_be(1, e, same))
        self.assertTrue(tf.could_be(1, e, {**same, "age": 600, "skills": (25,) * 5 + (0,)}))
        for change in ({"age": 499}, {"head": 2}, {"body": 5}, {"sex": 2}, {"skills": (20, 20, 19, 20, 20, 0)}):
            with self.subTest(change=change):
                self.assertFalse(tf.could_be(1, e, {**same, **change}))
        self.assertTrue(tf.could_be(1, tf.Entry(tf.PENDING, 9, "A"), {**same, "age": 0}))   # looks not known


LOG_BUILD = ROOT / "scripts" / "build_custom_title_log_harness.ps1"
LOG_HARNESS = ROOT / "native" / "population_export" / "custom_title_log_harness.c"
EXPORTER = ROOT / "native" / "population_export" / "population_export.c"


class CustomTitlesInTheLogs(unittest.TestCase):
    """The Village Population roster and the Village History print a
    villager's custom title under its name (the "patcher logs" the owner
    named), from the slot the log's own village header names."""

    def test_the_exporter_prints_the_title_from_the_slots_file(self):
        text = EXPORTER.read_text(encoding="utf-8")
        self.assertIn('#include "custom_titles.h"', text)
        self.assertIn("load_custom_titles(game_id, g, village);", text)
        self.assertIn('"  Custom title: %s\\n"', text)
        self.assertIn("vv_title_identity(record, g->name, g->name_capacity, g->likes,", text)

    def test_the_harness_covers_every_case(self):
        text = LOG_HARNESS.read_text(encoding="utf-8")
        for case in ("THE ROSTER PRINTS THE CUSTOM TITLE UNDER ITS VILLAGER'S NAME",
                     "A TITLE WHOSE RECORD HOLDS SOMEBODY ELSE IS NOT PRINTED",
                     "THE HISTORY PRINTS IT TOO",
                     "ANOTHER SLOT'S VILLAGE PRINTS NO TITLES",
                     "A NAME CONTAINING (Save 2) DOES NOT READ SLOT 2'S TITLES",
                     "THE LAST (Save N) MARKER IS THE SLOT"):
            with self.subTest(case=case):
                self.assertIn(case, text)

    @unittest.skipUnless(CL.exists(), "the 32-bit MSVC toolchain is not installed")
    def test_the_exporter_writes_it_on_real_files(self):
        run = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(LOG_BUILD)],
            capture_output=True, text=True, timeout=600)
        self.assertEqual(run.returncode, 0, run.stdout[-3000:] + run.stderr[-2000:])
        self.assertIn("0 failure(s)", run.stdout)
        self.assertNotIn("[FAIL]", run.stdout)
