"""Start Over clears the deleted logs' Like and Dislike Words boundaries (v1.35.78).

The owner's report (2026-10-19): Start Over did not clear the Like and Dislike Words. The
boundary files (native/shared/log_words.h; src/vv_save_layout.py words_files / words_file_for)
hold one "<offset>\\t<key>\\r\\n" line per log, keyed by the log's path inside the save folder,
and an exporter records a new boundary only when none is recorded. Start Over deleted the erased
village's logs but kept their lines, so the next village's log of the same name inherited the old
boundary and its correct words were treated as old ones.

The fix is in the Save Reset companion (native/shared/save_reset.c: delete_log_w and
forget_log_words): every log Start Over deletes has its lines removed from the save's own
boundary file, the shared one and an older build's "Log Words" one; every other line stays.

The proof is on real files: scripts/build_save_reset_words_harness.ps1 builds
native/shared/save_reset_words_harness.c with the real reset and runs it for all five games
(Documents redirected to a %TEMP% folder). These tests build and run it -- they fail, never skip,
when the 32-bit MSVC toolchain is missing -- and check the shipped DLL is the fixed build.
"""
from __future__ import annotations

import pathlib
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
RESET_C = ROOT / "native" / "shared" / "save_reset.c"
HARNESS = ROOT / "native" / "shared" / "save_reset_words_harness.c"
BUILD = ROOT / "scripts" / "build_save_reset_words_harness.ps1"
DLL_PATH = ROOT / "assets" / "save_reset" / "VVFP Save Reset.dll"
CL = pathlib.Path(
    r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC"
    r"\14.51.36231\bin\Hostx64\x86\cl.exe"
)

# Every game: the deleted logs' lines go, every other line stays, a new log gets boundary 0.
EVERY_GAME = (
    "A DELETED LOG'S BOUNDARY IS GONE (save's own file and the older shared one)",
    "a deleted shared log's boundary is gone from both shared files",
    "the save's own file keeps its kept Village History line, byte for byte",
    "ANOTHER SAVE'S BOUNDARY STAYS, byte for byte",
    "another save's boundary file is not rewritten at all",
    "the shared file keeps another village's line, byte for byte",
    "the older Log Words file keeps another village's line, byte for byte",
    "the kept Village History's boundary still counts",
    "no .tmp is left beside the rewritten file",
    "A NEW LOG REUSING THE NAME DOES NOT INHERIT THE OLD BOUNDARY (boundary 0)",
)
# A New Home and The Secret City are the two games whose words are tracked (log_words.h).
TRACKED_ONLY = ("the new log's boundary 0 is recorded in the save's own file",)


class StartOverWordsSourceTests(unittest.TestCase):
    def test_every_log_start_over_deletes_goes_through_delete_log_w(self) -> None:
        text = RESET_C.read_text(encoding="utf-8")
        self.assertIn('#include "log_words.h"', text)
        self.assertIn("(void)forget_log_words(game, slot, path);", text)
        # the population pages and the header-matched logs
        self.assertIn("removed += delete_log_w(game, slot, path);", text)
        self.assertEqual(text.count("removed += delete_log_w(game, slot, path_w);"), 7)
        # the boundary files: the save's own first, then the shared one and an older build's
        body = text[text.index("VV_RESET_STATIC int forget_log_words"):]
        body = body[: body.index("\n}\n")]
        self.assertLess(body.index("vv_log_words_save_path(game, slot"), body.index("vv_log_words_paths(game"))
        self.assertIn("forget_words_in(new_dat, key)", body)
        self.assertIn("forget_words_in(old_dat, key)", body)

    def test_the_harness_covers_every_case_in_every_game(self) -> None:
        text = HARNESS.read_text(encoding="utf-8")
        self.assertIn("for (game = 1; game <= 5; ++game)", text)
        for case in EVERY_GAME + TRACKED_ONLY:
            with self.subTest(case=case):
                self.assertIn(case, text)

    def test_the_shipped_dll_is_the_fixed_build(self) -> None:
        # The rewrite's temporary name is only in the fixed build.
        self.assertIn(b"%s.tmp", DLL_PATH.read_bytes())


class StartOverWordsHarnessRunsTests(unittest.TestCase):
    """The harness is BUILT AND RUN against the real reset, once, and read per game."""

    output = ""
    returncode = None

    @classmethod
    def setUpClass(cls) -> None:
        if not CL.is_file():
            raise AssertionError(f"the 32-bit MSVC toolchain is required to run this harness: {CL}")
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(BUILD)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        cls.output = result.stdout + result.stderr
        cls.returncode = result.returncode

    def test_the_harness_passes(self) -> None:
        self.assertEqual(self.returncode, 0, self.output)
        self.assertIn("OK (0 failures)", self.output)
        self.assertNotIn("[FAIL]", self.output)

    def _game(self, game: int) -> None:
        cases = EVERY_GAME + (TRACKED_ONLY if game in (1, 3) else ())
        for case in cases:
            with self.subTest(game=game, case=case):
                self.assertIn(f"[PASS] game {game}: {case}", self.output)

    def test_a_new_home(self) -> None:
        self._game(1)

    def test_the_lost_children(self) -> None:
        self._game(2)

    def test_the_secret_city(self) -> None:
        self._game(3)

    def test_the_tree_of_life(self) -> None:
        self._game(4)

    def test_new_believers(self) -> None:
        self._game(5)


if __name__ == "__main__":
    unittest.main()
