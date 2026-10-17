"""unicorn's access violations are its own, handled ones; emulator tests print no dumps.

unicorn 2.1 on Windows commits its JIT code buffer lazily: the first write into
each uncommitted 4 MB raises a first-chance access violation that unicorn's own
vectored exception handler resolves (tests/conftest.py explains it). With
faulthandler enabled -- pytest always enables it -- each one printed "Windows
fatal exception: access violation" and a traceback, although the process carried
on: about 15,900 dumps in one run of the emulator files, read as a crash.

It checks:

* the faults are survivable: with faulthandler on, many engines are opened,
  mapped and run, and the process exits normally;
* a pytest run of an emulator test prints no dump, also when the harness is
  imported inside the test (conftest pauses faulthandler when a test creates an
  engine);
* in this process, faulthandler is on, an engine pauses it, and it is back on
  for the next test.
"""
from __future__ import annotations

import faulthandler
import os
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DUMP = "Windows fatal exception"


def _run(args: list[str], timeout: int = 600) -> subprocess.CompletedProcess:
    # A checkout without the game files skips the child's tests; that is not a failure here.
    env = dict(os.environ, VVFP_ALLOW_NO_FIXTURES="1")
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=timeout, check=False, env=env)


@unittest.skipUnless(sys.platform == "win32", "the lazily committed JIT buffer is unicorn's Windows build")
class UnicornFaultsAreHandled(unittest.TestCase):
    def test_many_engines_survive_with_faulthandler_on(self) -> None:
        script = textwrap.dedent("""
            import faulthandler, gc
            faulthandler.enable(all_threads=True)
            from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
            for i in range(300):
                uc = Uc(UC_ARCH_X86, UC_MODE_32)
                uc.mem_map(0x400000, 0x1000)
                uc.mem_write(0x400000, b"\\x90" * 16)
                uc.emu_start(0x400000, 0x400010)
                del uc
                if i % 50 == 0:
                    gc.collect()
            print("survived")
        """)
        run = _run([sys.executable, "-c", script])
        self.assertEqual(run.returncode, 0, run.stderr[-2000:])
        self.assertIn("survived", run.stdout)

    def test_an_emulator_test_run_prints_no_dump(self) -> None:
        run = _run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                    "tests/test_vv5_statue_selector_executes.py"])
        output = run.stdout + run.stderr
        self.assertNotIn(DUMP, output)
        self.assertEqual(run.returncode, 0, output[-2000:])

    def test_a_harness_imported_inside_a_test_prints_no_dump(self) -> None:
        # test_reset_corrupted_skills_vv4_vv5 imports tests/story_emulator.py inside a helper.
        run = _run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                    "tests/test_reset_corrupted_skills_vv4_vv5.py",
                    "-k", "test_a_purchase_refused_for_tech_points_changes_nothing"])
        output = run.stdout + run.stderr
        self.assertNotIn(DUMP, output)
        self.assertEqual(run.returncode, 0, output[-2000:])


@unittest.skipUnless("pytest" in sys.modules, "conftest's switch is a pytest hook")
class FaulthandlerIsPausedOnlyForAnEngine(unittest.TestCase):
    # unittest runs these in name order.
    def test_1_on_before_an_engine(self) -> None:
        self.assertTrue(faulthandler.is_enabled())

    def test_2_an_engine_pauses_it(self) -> None:
        from unicorn import Uc, UC_ARCH_X86, UC_MODE_32

        uc = Uc(UC_ARCH_X86, UC_MODE_32)
        uc.mem_map(0x400000, 0x1000)
        self.assertFalse(faulthandler.is_enabled())

    def test_3_back_on_in_the_next_test(self) -> None:
        self.assertTrue(faulthandler.is_enabled())


if __name__ == "__main__":
    unittest.main()
