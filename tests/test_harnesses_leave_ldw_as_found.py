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
import tempfile
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
        tmp_before = set(Path(tempfile.gettempdir()).glob("vvhd_*"))
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(BUILD_PARENTAGE)],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout[-2000:] + result.stderr[-1000:])
        after = sorted(p.name for p in docs.iterdir()) if docs.is_dir() else None
        self.assertEqual(before, after)
        self.assertEqual(set(Path(tempfile.gettempdir()).glob("vvhd_*")) - tmp_before, set(),
                         "the throwaway Documents is removed at exit")

    def test_the_throwaway_documents_name_is_short_and_of_fixed_length(self) -> None:
        """The harnesses keep their files four folders below the throwaway Documents, in ANSI
        MAX_PATH buffers; a name built from a decimal process id and tick count grew with the
        machine's uptime and pushed the reconcile harness's counters backup past 260 characters."""
        header = (ROOT / "native" / "shared" / "harness_redirect_documents.h").read_text(encoding="utf-8")
        self.assertIn('"%svvhd_%08lX%08lX", temp, GetCurrentProcessId(),', header)
        self.assertNotIn("vvfp_harness_docs_", header)
        longest = ("Virtual Villagers Fun Patcher Data\\Copies Made Before Repairs\\Virtual Villagers Fun "
                   "Patcher Data\\Village Statistics\\Village Statistics - Save 1.dat.before-v1.35.58-repair")
        docs = Path(tempfile.gettempdir()) / ("vvhd_" + "F" * 16)
        self.assertLess(len(str(docs / "LDW" / "reconcile_harness" / longest)), 260)

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
    def test_the_ldw_harnesses_leave_the_real_ldw_listing_as_it_was(self) -> None:
        """The owner, 2026-10-10: no test or harness may ever write under the real Documents\\LDW, not even
        a folder of its own.  Runs two harnesses that drive shipped companions (the Deaths log's, which
        empties its log folders first, and New Believers' mask sidecar) and checks the real LDW listing,
        read only, is exactly what it was -- and that each throwaway Documents is gone afterwards."""
        import os
        import tempfile
        docs = Path(os.path.expanduser("~")) / "OneDrive" / "Documents" / "LDW"
        if not docs.is_dir():
            docs = Path(os.path.expanduser("~")) / "Documents" / "LDW"
        before = sorted(p.name for p in docs.iterdir()) if docs.is_dir() else None   # read-only
        tmp_before = set(Path(tempfile.gettempdir()).glob("vvhd_*"))
        for script in ("build_death_log_harness.ps1", "build_vv5_mask_identity_harness.ps1"):
            with self.subTest(script=script):
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                     str(ROOT / "scripts" / script)],
                    capture_output=True, text=True, timeout=600,
                )
                self.assertEqual(result.returncode, 0, result.stdout[-2000:] + result.stderr[-1000:])
        after = sorted(p.name for p in docs.iterdir()) if docs.is_dir() else None
        self.assertEqual(before, after)
        self.assertEqual(set(Path(tempfile.gettempdir()).glob("vvhd_*")) - tmp_before, set(),
                         "the throwaway Documents is removed at exit")

    def test_every_harness_that_can_reach_documents_is_redirected(self) -> None:
        """Every harness that loads a companion, resolves Documents or calls the save-folder helpers is
        pointed at a throwaway %TEMP% Documents before it does: through harness_ldw_tree.h (whose begin()
        redirects the whole process first), by calling harness_redirect_documents_process() as main()'s
        first statement, or by compiling the code under test with its folder lookup replaced."""
        reaches = re.compile(
            r"LoadLibrary|CSIDL_PERSONAL|\bvv_save_folder(?:_w)?\s*\(|\bvv_parentage_log_folder\s*\(|harness_ldw_tree\.h")
        compiled_in = re.compile(r"#define\s+(?:SHGetFolderPathA|SHGetFolderPathW|vv_save_folder_w)\s|^int vv_save_folder\(",
                                 re.M)
        for path in _harnesses():
            source = path.read_text(encoding="utf-8")
            if not reaches.search(source) or path.name == "harness_ldw_tree_harness.c":
                continue
            with self.subTest(harness=path.name):
                main = re.search(r"^int w?main\([^)]*\) \{\n(.*)$", source, re.M | re.S)
                body = main.group(1) if main else ""
                begin = body.find("harness_ldw_tree_begin();")
                load = body.find("LoadLibrary")
                via_tree = ("harness_ldw_tree.h" in source and 0 <= begin < 400
                            and (load < 0 or begin < load))
                via_process = "harness_redirect_documents_process()" in (main.group(1)[:600] if main else "")
                self.assertTrue(via_tree or via_process or compiled_in.search(source),
                                f"{path.name} can reach the real Documents unredirected")

    def test_the_tree_header_redirects_the_whole_process_first(self) -> None:
        text = HEADER.read_text(encoding="utf-8")
        begin = text[text.index("static void harness_ldw_tree_begin(void)"):]
        self.assertIn('#include "harness_redirect_documents.h"', text)
        redirect = begin.index("harness_redirect_documents_process()")
        self.assertLess(redirect, begin.index("HARNESS_LDW_DOCUMENTS(docs)"))
        self.assertIn("harness_ldw_refuse(", begin[redirect:redirect + 200], "an unredirected process must not run")
        redirect_header = (ROOT / "native" / "shared" / "harness_redirect_documents.h").read_text(encoding="utf-8")
        process = redirect_header[redirect_header.index("static int harness_redirect_documents_process(void)"):]
        for name in ("SHGetFolderPathA", "SHGetFolderPathW", "SHGetSpecialFolderPathA", "SHGetSpecialFolderPathW"):
            self.assertIn(f'harness_hotpatch("{name}"', process)


if __name__ == "__main__":
    unittest.main()
