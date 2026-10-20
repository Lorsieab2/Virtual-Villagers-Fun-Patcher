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
(Documents redirected to a %TEMP% folder). These tests build and run it wherever the 32-bit MSVC
toolchain is installed (elsewhere, CI included, they are skipped with that reason, like the other
reset harness's), and check the shipped DLL is the fixed build.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile
import threading
import time
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
    # one writer at a time (Codex, #597): an append made during the reset waits and is kept
    "a writer appended while the reset was replacing the file",
    "THE WRITER WAITED FOR THE RESET'S LOCK",
    "AN APPEND MADE DURING THE RESET IS KEPT, and the deleted log's line is still gone",
    # ...and the wait is bounded: the file is left as it was
    "with the lock held elsewhere the log is still deleted",
    "A LOCK NOT HAD IN TIME LEAVES THE BOUNDARY FILE UNTOUCHED",
    "...and the refusal is counted",
    "the reset waited the bounded time, no longer",
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
        blob = DLL_PATH.read_bytes()
        # the rewrite's per-process, per-operation temporary name, and the boundary lock
        self.assertIn(b"%s.%lu-%ld.tmp", blob)
        self.assertNotIn(b"%s.tmp\x00", blob)
        self.assertIn("Local\\VVFP Like and Dislike Words - Virtual Villagers %d".encode("utf-16-le"), blob)

    def test_the_rewrite_holds_the_lock_around_every_file(self) -> None:
        text = RESET_C.read_text(encoding="utf-8")
        body = text[text.index("VV_RESET_STATIC int forget_log_words"):]
        body = body[: body.index("\n}\n")]
        lock, unlock = body.index("vv_log_words_lock(game)"), body.index("vv_log_words_unlock(lock)")
        for call in ("forget_words_in(save_dat, key)", "forget_words_in(new_dat, key)", "forget_words_in(old_dat, key)"):
            with self.subTest(call=call):
                self.assertTrue(lock < body.index(call) < unlock)


class WordsLockTests(unittest.TestCase):
    """The patcher's own writers hold the same lock as the game's (src/vv_save_layout.py words_lock)."""

    LOG_WORDS_H = ROOT / "native" / "shared" / "log_words.h"

    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(ROOT / "src"))
        import vv_save_layout

        cls.layout = vv_save_layout

    def test_the_name_and_the_wait_are_the_game_companions_own(self) -> None:
        header = self.LOG_WORDS_H.read_text(encoding="utf-8")
        c_name = self.layout.WORDS_LOCK_NAME.replace("\\", "\\\\").replace("{game}", "%d")
        self.assertIn(f'#define VV_LOG_WORDS_LOCK_NAME L"{c_name}"', header)
        self.assertIn(f"#define VV_LOG_WORDS_LOCK_MS {self.layout.WORDS_LOCK_MS}", header)

    def _hold(self, game: int, seconds: float) -> tuple[threading.Thread, threading.Event]:
        taken = threading.Event()

        def holder() -> None:
            with self.layout.words_lock(game):
                taken.set()
                time.sleep(seconds)

        thread = threading.Thread(target=holder)
        thread.start()
        self.assertTrue(taken.wait(5))
        return thread, taken

    def test_a_held_lock_refuses_after_the_bounded_wait(self) -> None:
        for game in range(1, 6):
            with self.subTest(game=game):
                thread, _ = self._hold(game, 1.0)
                started = time.monotonic()
                with self.assertRaises(self.layout.WordsLockTimeout):
                    with self.layout.words_lock(game, timeout_ms=200):
                        pass
                self.assertLess(time.monotonic() - started, 0.9)
                thread.join()
                with self.layout.words_lock(game, timeout_ms=200):
                    pass                                   # free again once released

    def test_the_patchers_append_waits_for_the_lock_and_is_written(self) -> None:
        import vv_log_tools as tools

        for game in (1, 3):                                # the games whose words are tracked
            with self.subTest(game=game), tempfile.TemporaryDirectory() as tmp:
                folder = pathlib.Path(tmp)
                log = (folder / "Virtual Villagers Fun Patcher Logs" / "Births and Conceptions"
                       / f"Virtual Villagers {game} Births and Conceptions Log 1.txt")
                log.parent.mkdir(parents=True)
                log.write_bytes(b"Village: Kalahuna (Save 1)\r\n")
                thread, _ = self._hold(game, 0.5)
                started = time.monotonic()
                tools.new_log_words(folder, log)
                waited = time.monotonic() - started
                thread.join()
                self.assertGreater(waited, 0.3, "the append did not wait for the held lock")
                key = str(log.relative_to(folder))
                dat = self.layout.words_file_for(folder, game, key)
                self.assertEqual(dat.read_bytes(), f"0\t{key}\r\n".encode("utf-8"))

    def test_every_patcher_writer_takes_the_lock(self) -> None:
        src = ROOT / "src"
        for module, needle in (
            ("vv_log_tools.py", "with layout.words_lock(game):\n        _move_word_boundary("),
            ("vv_log_tools.py", "with layout.words_lock(game):                         # across the check"),
            ("vv_log_tools.py", "with layout.words_lock(game), open(dat, \"ab\") as boundaries:"),
            ("vv_move_to_save_folders.py", "with layout.words_lock_for(path):            # the game's Start Over"),
            ("vv_move_to_save_folders.py", "            with layout.words_lock_for(path):\n                if before is None:"),
            ("vv_move_old_names.py", "with layout.words_lock(game):    # the game's Start Over rewrites this file"),
            ("vv_history_revision.py", "with tools.layout.words_lock_for(path):"),
        ):
            with self.subTest(module=module, needle=needle):
                self.assertIn(needle, (src / module).read_text(encoding="utf-8"))


@unittest.skipUnless(CL.is_file(), f"the 32-bit MSVC toolchain is not installed ({CL}); "
                     "the on-disk Start Over words harness cannot be built here")
class StartOverWordsHarnessRunsTests(unittest.TestCase):
    """The harness is BUILT AND RUN against the real reset, once, and read per game.

    Gated on the compiler exactly as SaveResetHarnessRunsTests is (CI has none), with the reason
    shown in the skip; wherever the toolchain is installed it always runs."""

    output = ""
    returncode = None

    @classmethod
    def setUpClass(cls) -> None:
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
