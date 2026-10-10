"""Each kind of patcher data file lives in its own folder.

The owner: "please put the dat files that the games make into their
appropriate folders in the games' save directories."

Four kinds used to be written loose in "Virtual Villagers Fun Patcher Data"
and now each has a folder of its own (native/shared/data_subfolder.h):

    Village Masks          the Origins mask tables (all five games)
    Graves                 Cause of Death's graves (A New Home, The Lost Children)
    Parents (A New Home)   A New Home's parent records ("Parentage Records" before 2026-10-09)
    Unaccounted Villagers  Cause of Death's villagers at the last save (all five games)

The rules -- a loose copy is MOVED in, never over an existing file; when both
exist the folder's copy is used and the loose one is left alone; when the move
fails the loose copy stays in use for reading and writing -- are proved
against real files by two harnesses:

  * data_subfolder_harness.c drives the resolver itself (ten scenarios,
    including an injected move failure, a real one from a locked file, a race,
    and a file that cannot be examined), and the companions' atomic write on
    the path it returns;
  * data_writer_paths_harness.c compiles each writer's REAL source and calls
    its real path builder (masks x5, parentage, graves, roster), with the
    Documents folder redirected to %TEMP%.

Start Over at both places is save_reset_harness.c's (run by
test_village_history_and_log_folders.py), and the Cause of Death files'
move-and-read by cause_files_harness.c (run by
test_deaths_log_and_graves_file.py). These checks keep every writer on the
resolver and the reset list complete.
"""
from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEADER = ROOT / "native" / "shared" / "data_subfolder.h"
RESET = ROOT / "native" / "shared" / "save_reset.c"
CL = Path(
    r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC"
    r"\14.51.36231\bin\Hostx64\x86\cl.exe"
)

# writer source -> (path builder, the folder it must use)
WRITERS = {
    "native/vv1_origins_icons/vv1_origins_icons.c": ("vv1_mask_sidecar_path", "VV_DATA_SUB_MASKS"),
    "native/vv2_origins_icons/vv2_origins_icons.c": ("vv2_mask_sidecar_path_slot", "VV_DATA_SUB_MASKS"),
    "native/vv3_full_mastery_candidate/vv3_full_mastery_candidate.c": ("vv3_mask_sidecar_path", "VV_DATA_SUB_MASKS"),
    "native/vv4_origins_icons/vv4_origins_icons.c": ("vv_build_sidecar_path", "VV_DATA_SUB_MASKS"),
    "native/vv5_task9_origins/vv5_task9_origins.c": ("build_mask_sidecar_path", "VV_DATA_SUB_MASKS"),
    "native/vv1_parentage/vv1_parentage.c": ("vv1_parents_path", "VV_DATA_SUB_PARENTAGE"),
    "native/vvfp_cause_of_death/cod_vv12.inc": ("cod_build_path", "VV_DATA_SUB_GRAVES"),
    "native/vvfp_cause_of_death/cod_roster.inc": ("roster_build_path", "VV_DATA_SUB_UNACCOUNTED"),
}

FOLDER_NAMES = {
    "VV_DATA_SUB_MASKS": "Village Masks",
    "VV_DATA_SUB_GRAVES": "Graves",
    # "Parentage Records" in older builds (native/shared/save_layout.h; the owner, 2026-10-09)
    "VV_DATA_SUB_PARENTAGE": "Parents (A New Home)",
    "VV_DATA_SUB_UNACCOUNTED": "Unaccounted Villagers",
}

# (game, folder macro, file stem) for every per-save file of these kinds -- Start Over also names the
# place an older build kept it (native/shared/save_layout.h), while it has not moved.
KINDS = [
    (1, "VV_DATA_SUB_MASKS", "Virtual Villagers 1 Village Masks"),
    (2, "VV_DATA_SUB_MASKS", "Virtual Villagers 2 Village Masks"),
    (3, "VV_DATA_SUB_MASKS", "Village Masks"),
    (4, "VV_DATA_SUB_MASKS", "Village Masks"),
    (5, "VV_DATA_SUB_MASKS", "Village Masks"),
    (1, "VV_DATA_SUB_PARENTAGE", "Virtual Villagers 1 Parentage Records"),
    (1, "VV_DATA_SUB_PARENTAGE_OLD", "Virtual Villagers 1 Parentage Records"),
    (1, "VV_DATA_SUB_GRAVES", "Virtual Villagers 1 Graves"),
    (2, "VV_DATA_SUB_GRAVES", "Virtual Villagers 2 Graves"),
] + [(n, "VV_DATA_SUB_UNACCOUNTED", f"Virtual Villagers {n} Villagers at Last Save") for n in range(1, 6)] \
  + [(n, "VV_DATA_SUB_UNACCOUNTED", f"Virtual Villagers {n} Village Roster") for n in range(1, 6)]


def function(source: str, name: str) -> str:
    match = re.search(r"^static int " + re.escape(name) + r"\(.*?^}", source, re.M | re.S)
    assert match, name
    return match.group(0)


def run_script(name: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts" / name)],
        capture_output=True,
        text=True,
        timeout=1800,
    )


class DatFilesInSubfolders(unittest.TestCase):
    def test_the_folder_names_are_the_owners(self) -> None:
        header = HEADER.read_text(encoding="utf-8")
        self.assertIn('#define VV_DATA_FOLDER "Virtual Villagers Fun Patcher Data"', header)
        for macro, name in FOLDER_NAMES.items():
            with self.subTest(macro=macro):
                self.assertRegex(header, r"#define " + macro + r'\s+"' + re.escape(name) + '"')
        self.assertRegex(header, r'#define VV_DATA_SUB_PARENTAGE_OLD\s+"Parentage Records"')

    def test_a_loose_file_is_never_moved_over_another(self) -> None:
        header = HEADER.read_text(encoding="utf-8")
        self.assertIn("MoveFileExA((from), (to), MOVEFILE_WRITE_THROUGH)", header)
        # The flag is named only in prose ("No MOVEFILE_REPLACE_EXISTING,
        # ever."), never passed to a call.
        self.assertNotRegex(header, r"[|(,]\s*MOVEFILE_REPLACE_EXISTING|MOVEFILE_REPLACE_EXISTING\s*[|)]")
        self.assertNotIn("DeleteFile", header)
        self.assertNotIn("CopyFile", header)

    def test_every_writer_resolves_through_the_shared_rule(self) -> None:
        for relative, (builder, macro) in WRITERS.items():
            with self.subTest(writer=relative):
                body = function((ROOT / relative).read_text(encoding="utf-8"), builder)
                self.assertRegex(body, r"vv_data_file_path\(out, [^,]+, " + macro + r", name,")
                # No path to the old loose place is formatted by hand any more.
                self.assertNotRegex(body, r'Fun Patcher Data\\\\(?:Virtual Villagers \d |Village Masks)')

    def test_start_over_names_both_places_for_every_kind(self) -> None:
        reset = RESET.read_text(encoding="utf-8")
        table = reset.split("static const char *const SIDECAR_FORMATS", 1)[1].split("};", 1)[0]
        rows = re.findall(r"/\* VV(\d) \*/ \{(.*?)\}", table, re.S)
        self.assertEqual([int(n) for n, _ in rows], [1, 2, 3, 4, 5])
        by_game = {int(n): row for n, row in rows}
        for game, macro, stem in KINDS:
            with self.subTest(game=game, stem=stem):
                row = by_game[game]
                self.assertIn(f'DATA_FORMAT({macro}, "{stem}")', row)
                if macro == "VV_DATA_SUB_GRAVES":
                    self.assertIn(f'CAUSE_OF_DEATH_FORMAT("{game}")', row)
                elif macro == "VV_DATA_SUB_UNACCOUNTED":
                    self.assertIn(f'ROSTER_FORMAT("{game}")', row)
                else:
                    self.assertIn(f'Fun Patcher Data\\\\{stem} - Save %d.dat"', row)
        self.assertIn(
            '#define DATA_FORMAT(sub, name) \\\n'
            '    "%s\\\\Virtual Villagers Fun Patcher Data\\\\" sub "\\\\" name " - Save %d.dat"',
            reset,
        )

    @unittest.skipUnless(CL.is_file(), "the 32-bit MSVC toolchain is not installed")
    def test_the_resolver_harness_passes(self) -> None:
        result = run_script("build_data_subfolder_harness.ps1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("all checks passed", result.stdout)
        self.assertNotIn("FAIL", result.stdout)
        self.assertEqual(result.stdout.count("  ok   "), 39)

    @unittest.skipUnless(CL.is_file(), "the 32-bit MSVC toolchain is not installed")
    def test_every_writers_real_path_builder(self) -> None:
        result = run_script("build_data_writer_paths_harness.ps1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("FAIL", result.stdout)
        self.assertEqual(result.stdout.count("all checks passed"), 8)
        for macro, name in FOLDER_NAMES.items():
            self.assertIn(f"<Data>\\{name}\\<name>", result.stdout)
        # A New Home's parents in a file older still (loose, or vv1_parents_S.dat) go into "Parentage
        # Records", which a game still patched by v1.35.63 reads too -- never into the new name (the
        # owner, 2026-10-09: "recognize old and new paths/folders/files alike").
        self.assertIn("b. a loose copy: the folder's path (Parentage Records)", result.stdout)
        self.assertEqual(result.stdout.count("b. a loose copy: the folder's path (Parentage Records)"), 2)


if __name__ == "__main__":
    unittest.main()
