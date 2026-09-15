"""The executable-name wrapper must not reach the builds it crashes.

The wrapper rewrites `GetModuleFileNameA` so a renamed build reports the stock
basename. VV1, VV2 and VV3 need it and their shipped builds run with it. VV4
and VV5 do not survive it: the wrapped build faults `0xC0000005` during startup
inside `_strncpy`, on a Source argument holding a small integer instead of an
address.

That was established by running the executables, not by reading them. Holding
the feature set and the game folder constant and varying only the wrapper and
the filename:

    wrapper  name        VV4          VV5
    -------  ----------  -----------  -----------
    no       stock       runs         -
    no       - Modded    runs         runs
    yes      stock       0xC0000005   -
    yes      - Modded    0xC0000005   0xC0000005

The wrapped rows reproduce the shipped builds byte for byte, and the unwrapped
"- Modded" rows are the renamed case the wrapper exists to protect -- they
start and keep running without it.

These tests pin the exemption itself. They deliberately do not assert anything
about VV1/VV2/VV3 beyond "still guarded", because the measurements above are
not evidence about those games and the wrapper must keep reaching them.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as patcher  # noqa: E402


class NameCrashImmunityExemptionTests(unittest.TestCase):
    def test_only_the_two_crashing_builds_are_exempt(self) -> None:
        self.assertEqual(
            set(patcher.NAME_CRASH_IMMUNITY_EXEMPT_BUILD_IDS),
            {"vv4", "vv5"},
        )

    def test_the_games_that_run_with_the_wrapper_keep_it(self) -> None:
        """VV1/VV2/VV3 ship with the wrapper and start; do not widen this."""
        for build_id in ("vv1", "vv2", "vv3"):
            with self.subTest(build=build_id):
                self.assertNotIn(
                    build_id, patcher.NAME_CRASH_IMMUNITY_EXEMPT_BUILD_IDS
                )

    def test_every_exempt_id_is_a_real_build(self) -> None:
        known = {build.id for build in patcher.load_builds()}
        for build_id in patcher.NAME_CRASH_IMMUNITY_EXEMPT_BUILD_IDS:
            with self.subTest(build=build_id):
                self.assertIn(build_id, known)

    def test_publication_consults_the_exemption_at_every_call_site(self) -> None:
        """Each `_require_name_crash_immunity` call must be gated.

        An ungated call site would put the wrapper back into VV4/VV5 for
        whichever publication path used it, which is the crash. Asserting on
        the source keeps that true for call sites added later.
        """
        source = (ROOT / "src" / "vv_fun_patcher.py").read_text(encoding="utf-8")
        lines = source.splitlines()
        calls = [
            index
            for index, line in enumerate(lines)
            if "_require_name_crash_immunity(patched" in line
        ]
        self.assertTrue(calls, "no publication call sites found")
        for index in calls:
            with self.subTest(line=index + 1):
                self.assertIn(
                    "NAME_CRASH_IMMUNITY_EXEMPT_BUILD_IDS",
                    lines[index - 1],
                    "call site is not gated by the exemption set",
                )


if __name__ == "__main__":
    unittest.main()
