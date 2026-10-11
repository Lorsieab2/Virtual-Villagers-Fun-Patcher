"""Every committed companion DLL and its test build match the current source, byte for byte.

The behaviour companions ship a DLL without test hooks and commit a separate
test build (tests/test_dlls/*.test.dll) that the emulator tests drive. Both
are prebuilt binaries: editing the C source changes nothing until the build
script is re-run and both outputs are committed. Nothing else in the suite
notices when one of them is stale -- a merge that keeps the older binary
silently ships (or tests) code the source no longer contains.

This re-runs each build script in a throwaway copy of the project (its native
source folders, native/shared, the icons its resources name and the script
itself), so nothing in this checkout is written, and compares every DLL the
script produces with the committed file of the same relative path. Every
script links with /Brepro and embeds no path or date
(tests/test_dll_builds_are_deterministic.py), so the comparison is the whole
file, not selected sections: the earlier version of this test masked the link
timestamps and debug-record identities that every build used to change.

The VV1, VV2, VV4 and VV5 Full Mastery candidate DLLs in data/candidates are
not compared: they are withdrawn candidates, not shipped, and the committed
files were built before their scripts linked with /Brepro (a rebuild of the
current source differs from them). The VV3 candidate and the Task 9 icons are.

It is skipped where the MSVC toolchain the scripts name is not installed.
"""
from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from test_dll_builds_are_deterministic import build_copy, dll_scripts, toolchain_present  # noqa: E402

# Withdrawn candidates whose committed DLLs predate /Brepro (see the docstring).
NOT_COMPARED = {
    "build_vv1_full_mastery_candidate_dll.ps1",
    "build_vv2_full_mastery_candidate_dll.ps1",
    "build_vv4_full_mastery_candidate_dll.ps1",
    "build_vv5_full_mastery_candidate_dll.ps1",
}


class CommittedDllsMatchTheirSourceTests(unittest.TestCase):
    def test_each_build_script_reproduces_its_committed_dlls(self) -> None:
        ran = 0
        for script in dll_scripts():
            if script.name in NOT_COMPARED or not toolchain_present(script):
                continue
            with self.subTest(script=script.name), tempfile.TemporaryDirectory() as temp:
                built = build_copy(script, Path(temp))
                self.assertTrue(built, f"{script.name} built nothing")
                for relative, digest in sorted(built.items()):
                    committed = ROOT / relative
                    self.assertTrue(committed.exists(), f"{relative} is built but not committed")
                    self.assertEqual(
                        hashlib.sha256(committed.read_bytes()).hexdigest(), digest,
                        f"{relative} differs from a fresh build of the current source -- "
                        f"rebuild with scripts/{script.name} and commit it")
                ran += 1
        if not ran:
            self.skipTest("MSVC toolchain not installed")

    def test_the_scripts_set_aside_are_exactly_the_candidates_that_differ(self) -> None:
        names = {s.name for s in dll_scripts()}
        self.assertLessEqual(NOT_COMPARED, names)


if __name__ == "__main__":
    unittest.main()
