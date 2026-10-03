"""Every harness that writes into the real Documents\\LDW removes what it made.

A harness that drives a shipped companion makes that companion write where it
would in a game -- Documents\\LDW\\<harness name>\\... -- which is the
player's real save folder. Two harnesses left eight empty folders there per
run (measured before native/shared/harness_ldw_tree.h existed): the
companion's log and data folders and the per-harness folder itself.

The header records at start-up which of those folders already exist and, at
exit (normal, exit() or a crash), removes only what the run created. These
checks keep every such harness wired to it: the include, the call as the first
statement of main(), and no ExitProcess() that would skip the exit handler.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEADER = ROOT / "native" / "shared" / "harness_ldw_tree.h"

# A harness writes under the real Documents folder when it resolves it
# itself (CSIDL_PERSONAL) or calls the shared folder helpers unredirected.
WRITES_DOCUMENTS = re.compile(
    r"CSIDL_PERSONAL|\bvv_save_folder(?:_w)?\s*\(|\bvv_parentage_log_folder\s*\("
)
# Harnesses that point the folder helpers somewhere else first, by macro or
# by defining their own vv_save_folder over a %TEMP% folder.
REDIRECTED = re.compile(
    r"#define\s+(?:SHGetFolderPathA|vv_save_folder_w)\s|^int vv_save_folder\(", re.M
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
                "native/parentage_export/parentage_export_harness.c",
                "native/parentage_export/pending_harness.c",
                "native/parentage_export/select_holes_harness.c",
                "native/parentage_export/village_publisher_harness.c",
                "native/population_export/population_export_harness.c",
                "native/shared/save_reset_harness.c",
                "native/vv5_task9_origins/vv5_mask_identity_harness.c",
                "native/vvfp_cause_of_death/cause_files_harness.c",
            },
        )

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

    def test_the_header_only_removes_files_in_a_tree_it_created(self) -> None:
        text = HEADER.read_text(encoding="utf-8")
        end = text[text.index("static void harness_ldw_tree_end(void)"):]
        end = end[: end.index("\n}\n")]
        # Files are deleted only by the owned sweep, i.e. when the per-harness
        # folder did not exist before the run.
        self.assertIn("} else if (!harness_ldw_tree_existed) {\n        harness_ldw_sweep(harness_ldw_tree, 1);", end)
        self.assertIn("harness_ldw_sweep(harness_ldw_tree, 0);", end)
        self.assertIn("if (!harness_ldw_root_existed) RemoveDirectoryA(harness_ldw_root);", end)
        sweep = text[text.index("static void harness_ldw_sweep("):]
        sweep = sweep[: sweep.index("\n}\n")]
        self.assertIn("} else if (owned) {", sweep)
        self.assertIn("if (owned || !harness_ldw_was_kept(path)) RemoveDirectoryA(path);", sweep)
        # The paths come from the Documents folder and the exe's own name at
        # run time, never from a fixed machine path.
        self.assertIn("SHGetSpecialFolderPathA(NULL, docs, CSIDL_PERSONAL, FALSE)", text)
        self.assertIn("GetModuleFileNameA(NULL, exe, MAX_PATH)", text)
        self.assertNotRegex(text, r"[A-Za-z]:\\\\")  # no drive-letter path
        self.assertIn("atexit(harness_ldw_tree_end);", text)
        self.assertIn("SetUnhandledExceptionFilter(harness_ldw_on_crash);", text)


if __name__ == "__main__":
    unittest.main()
