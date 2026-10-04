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
            "two villagers sharing the title's identity: neither is given it",
            "a surviving Kai is not given either Kai's title",
            "... and the file still loads with both entries (no record listed twice)",
            "AN IDENTITY TWO VILLAGERS SHARE IS NOT KEPT ON THE TITLE'S OLD RECORD: neither shows it",
            "A PURE MOVE IS WRITTEN BACK: the next session finds Kai's title at record 0",
            "... and the entry is not moved onto either of them (still record 2)",
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
