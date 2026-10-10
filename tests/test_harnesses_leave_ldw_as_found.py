"""Every harness that writes into the real Documents\\LDW removes what it made.

A harness that drives a shipped companion makes that companion write where it
would in a game -- Documents\\LDW\\<harness name>\\... -- which is the
player's real save folder. Two harnesses left eight empty folders there per
run (measured before native/shared/harness_ldw_tree.h existed): the
companion's log and data folders and the per-harness folder itself.

The header serialises every harness run (one Global\\ lock per Documents folder), refuses to
run at all when the harness's folder already exists -- several harnesses
start by emptying it -- and, at exit (normal, exit() or a crash), removes the
folder the run created, never entering or removing a junction. These checks keep every such
harness wired to it -- the include, the call as the first statement of
main(), no ExitProcess() that would skip the exit handler -- and run the
header itself against a throwaway Documents folder.
"""
from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEADER = ROOT / "native" / "shared" / "harness_ldw_tree.h"
BUILD = ROOT / "scripts" / "build_harness_ldw_tree_harness.ps1"
BUILD_PARENTAGE = ROOT / "scripts" / "build_parentage_export_harness.ps1"
CL = Path(
    r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC"
    r"\14.51.36231\bin\Hostx64\x86\cl.exe"
)

# A harness writes under the real Documents folder when it resolves it
# itself (CSIDL_PERSONAL) or calls the shared folder helpers unredirected.
WRITES_DOCUMENTS = re.compile(
    r"CSIDL_PERSONAL|\bvv_save_folder(?:_w)?\s*\(|\bvv_parentage_log_folder\s*\("
)
# Harnesses that point the folder helpers somewhere else first, by macro or
# by defining their own vv_save_folder over a %TEMP% folder.
REDIRECTED = re.compile(
    r"#define\s+(?:SHGetFolderPathA|vv_save_folder_w)\s|^int vv_save_folder\(|\bharness_redirect_documents\(", re.M
)


def _harnesses() -> list[Path]:
    return sorted((ROOT / "native").glob("*/*harness*.c"))


def _writes_ldw(source: str) -> bool:
    return bool(WRITES_DOCUMENTS.search(source)) and not REDIRECTED.search(source)


class HarnessesLeaveLdwAsFound(unittest.TestCase):
    def test_the_set_of_ldw_harnesses_is_the_measured_one(self) -> None:
        found = {
            path.relative_to(ROOT).as_posix()
            for path in _harnesses()
            if _writes_ldw(path.read_text(encoding="utf-8"))
        }
        self.assertEqual(
            found,
            {
                "native/parentage_export/death_log_harness.c",
                "native/parentage_export/pending_harness.c",
                "native/parentage_export/select_holes_harness.c",
                "native/parentage_export/village_publisher_harness.c",
                "native/population_export/population_export_harness.c",
                "native/shared/save_reset_harness.c",
                "native/vv5_task9_origins/vv5_mask_identity_harness.c",
                "native/vvfp_cause_of_death/cause_files_harness.c",
                "native/vvfp_cause_of_death/grave_backfill_harness.c",
                "native/vvfp_cause_of_death/arrival_harness.c",
                "native/statistics_export/reconcile_harness.c",
            },
        )

    def test_the_parentage_export_harness_never_touches_the_real_documents(self) -> None:
        """It LoadLibrary()s the shipped DLL, which writes under <Documents>\\LDW\\<exe name>.  Cleaning up at
        exit is not enough: a run killed part-way (a cancelled test run) left its folders in the owner's
        real OneDrive\\Documents\\LDW.  So the DLL's own shell32 imports are patched to answer CSIDL_PERSONAL
        with a throwaway %TEMP% folder (native/shared/harness_redirect_documents.h), before the DLL resolves
        any folder; a killed run then leaves only an unreferenced %TEMP% folder."""
        harness = (ROOT / "native" / "parentage_export" / "parentage_export_harness.c").read_text(encoding="utf-8")
        header = (ROOT / "native" / "shared" / "harness_redirect_documents.h").read_text(encoding="utf-8")
        self.assertIn('#include "../shared/harness_redirect_documents.h"', harness)
        self.assertNotIn("CSIDL_PERSONAL", harness)
        self.assertNotIn("SHGetSpecialFolderPathA(", harness)
        load = harness.index("LoadLibraryA(argv[1])")
        redirect = harness.index("harness_redirect_documents(dll)")
        locate = harness.index("locate_folder()", redirect)
        self.assertLess(load, redirect)
        self.assertLess(redirect, locate)
        self.assertIn("return 2", harness[redirect:redirect + 160], "an unredirected DLL must not run")
        for name in ("SHGetFolderPathA", "SHGetFolderPathW", "SHGetSpecialFolderPathA", "SHGetSpecialFolderPathW"):
            self.assertIn(f'"{name}"', header)
        self.assertIn("GetTempPathA", header)
        self.assertIn("atexit(harness_docs_cleanup)", header)

    @unittest.skipUnless(CL.is_file(), "the 32-bit MSVC toolchain is not installed")
    def test_the_parentage_export_harness_leaves_the_real_ldw_listing_as_it_was(self) -> None:
        import os
        import tempfile
        docs = Path(os.path.expanduser("~")) / "OneDrive" / "Documents" / "LDW"
        if not docs.is_dir():
            docs = Path(os.path.expanduser("~")) / "Documents" / "LDW"
        before = sorted(p.name for p in docs.iterdir()) if docs.is_dir() else None   # read-only
        tmp_before = set(Path(tempfile.gettempdir()).glob("vvfp_harness_docs_*"))
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(BUILD_PARENTAGE)],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout[-2000:] + result.stderr[-1000:])
        after = sorted(p.name for p in docs.iterdir()) if docs.is_dir() else None
        self.assertEqual(before, after)
        self.assertEqual(set(Path(tempfile.gettempdir()).glob("vvfp_harness_docs_*")) - tmp_before, set(),
                         "the throwaway Documents is removed at exit")

    def test_each_ldw_harness_cleans_up_from_its_first_statement(self) -> None:
        for path in _harnesses():
            source = path.read_text(encoding="utf-8")
            if not _writes_ldw(source):
                continue
            with self.subTest(harness=path.name):
                self.assertRegex(source, r'#include "(?:\.\./shared/)?harness_ldw_tree\.h"')
                main = re.search(r"^int w?main\([^)]*\) \{\n(.*)$", source, re.M | re.S)
                self.assertIsNotNone(main, "no main()")
                first = main.group(1).lstrip().split("\n", 1)[0]
                self.assertTrue(
                    first.startswith("harness_ldw_tree_begin();"),
                    f"main() must start with harness_ldw_tree_begin(), got: {first!r}",
                )
                self.assertNotIn(
                    "ExitProcess(", source,
                    "ExitProcess skips the exit handler that removes the folders",
                )

    def test_the_header_resolves_its_paths_wide_and_at_run_time(self) -> None:
        text = HEADER.read_text(encoding="utf-8")
        # Wide, like the companions' own paths, and never a fixed machine path.
        self.assertIn("SHGetFolderPathW(NULL, CSIDL_PERSONAL, NULL, 0, (buffer))", text)
        self.assertIn("GetModuleFileNameW(NULL, exe, HARNESS_LDW_PATH)", text)
        self.assertNotRegex(text, r"\b(?:FindFirstFileA|RemoveDirectoryA|DeleteFileA|GetFileAttributesA)\b")
        self.assertNotRegex(text, r"[A-Za-z]:\\\\")  # no drive-letter path
        self.assertIn("atexit(harness_ldw_tree_end);", text)
        self.assertIn("SetUnhandledExceptionFilter(harness_ldw_on_crash);", text)

    def test_one_global_lock_keyed_to_documents_comes_before_any_existence_check(self) -> None:
        """Every harness, in every Windows session, shares one lock per
        Documents folder, so whether LDW and LDW\\<harness> existed is decided
        by one run at a time. A per-harness or per-session (Local\\) lock let
        two different harnesses, or one harness in two sessions, overlap."""
        text = HEADER.read_text(encoding="utf-8")
        begin = text[text.index("static void harness_ldw_tree_begin(void)"):]
        self.assertIn('L"Global\\\\vvfp-harness-ldw-%016llx", hash', begin)
        self.assertNotIn("Local\\\\", text)
        # The key is the case-folded Documents path, not the harness name.
        self.assertIn("LCMapStringEx(LOCALE_NAME_INVARIANT, LCMAP_LOWERCASE, docs, -1,", begin)
        self.assertIn("for (c = folded; *c; ++c) {", begin)
        lock = begin.index("mutex = CreateMutexW(NULL, FALSE, name);")
        wait = begin.index("WaitForSingleObject(mutex, INFINITE)")
        self.assertLess(lock, wait)
        for check in ("harness_ldw_exists(harness_ldw_tree)", "harness_ldw_exists(harness_ldw_root)"):
            self.assertLess(wait, begin.index(check), check)
        # A lock that cannot be had is a refusal, never an unprotected run.
        self.assertIn('harness_ldw_refuse(L"cannot take the harness lock for ", docs);', begin)

    @unittest.skipUnless(CL.is_file(), "the 32-bit MSVC toolchain is not installed")
    def test_the_header_keeps_everything_that_was_there(self) -> None:
        """Runs the header for real against a throwaway Documents folder:
        a junction LDW and a junction harness folder survive with their
        targets, a junction the run makes inside its own tree is never
        entered, nothing pre-existing is removed (an empty folder included),
        no file in a pre-existing tree is deleted, an exit() or a crash still
        cleans up, and an overlapping second run waits rather than having its
        files swept by the first. Each was seen failing against a mutated
        header (and the first and last against the previous header)."""
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(BUILD)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("== 0 failure(s) ==", result.stdout)
        for scenario in ("absent", "junction", "tree-link", "pre-tree", "pre-root",
                         "link-inside", "exit", "crash", "overlap", "case", "names"):
            self.assertIn(f"== {scenario}:", result.stdout)

    @unittest.skipUnless(CL.is_file(), "the 32-bit MSVC toolchain is not installed")
    def test_death_log_harness_never_empties_a_folder_it_did_not_make(self) -> None:
        """The death-log harness starts by deleting every .txt in its log
        folders. Pre-seed one there, in the real Documents\\LDW the harness
        itself writes to, and run the real harness: it must refuse to start
        and leave the file alone. The seed is this test's own file, in the
        harness's own folder; if that folder already exists the test does not
        touch it."""
        import ctypes
        import tempfile

        buffer = ctypes.create_unicode_buffer(1024)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buffer) != 0:
            self.skipTest("Documents cannot be resolved")
        folder = Path(buffer.value) / "LDW" / "death_log_harness"
        if folder.exists():
            self.skipTest(f"{folder} already exists; not touching it")
        with tempfile.TemporaryDirectory() as out:
            built = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                 str(ROOT / "scripts" / "build_death_log_harness.ps1"), "-OutDir", out],
                capture_output=True, text=True, timeout=300,
            )
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            self.assertFalse(folder.exists(), "a normal run left its folder behind")
            deaths = folder / "Virtual Villagers Fun Patcher Logs" / "Deaths"
            deaths.mkdir(parents=True)
            seed = deaths / "Virtual Villagers 1 Deaths Log 1.txt"
            seed.write_text("not the harness's\n", encoding="utf-8")
            try:
                run = subprocess.run(
                    [str(Path(out) / "death_log_harness.exe"),
                     str(ROOT / "assets" / "parentage" / "VVFP Parentage Export.dll")],
                    capture_output=True, text=True, timeout=120,
                )
                self.assertEqual(run.returncode, 2, run.stdout + run.stderr)
                self.assertIn("already exists", run.stderr)
                self.assertEqual(seed.read_text(encoding="utf-8"), "not the harness's\n")
            finally:
                seed.unlink(missing_ok=True)
                for empty in (deaths, deaths.parent, folder):
                    try:
                        empty.rmdir()
                    except OSError:
                        pass

if __name__ == "__main__":
    unittest.main()
