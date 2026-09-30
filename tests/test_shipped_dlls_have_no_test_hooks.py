"""Nothing debug-only reaches a shipped companion DLL.

The owner's rule: no cheated odds, debug logging, test hooks or debug strings
in builds.json, companion DLLs, assets or release zips.  Several companions
used to export the seams their tests drive -- `...ProbeSite`, `...ProbePick`
(which reseeded the live RNG), `...ProbeSelect` (which rewrote the golden
mushroom's game and sprite state), and the `...Stats` counters every stub
incremented on the game's own thread -- straight out of the shipped DLL.

Those now compile only into a TEST build of the same source (`VVFP_TEST`,
`native/<dll>/<dll>_test.def`), which each DLL's own build script writes to
`tests/test_dlls/` beside the shipped one.  The emulator tests and the C
harnesses drive that build, and its code is the code that used to ship.

This file keeps it that way:

* no DLL under assets/ or data/ -- everything a public patch can deploy --
  exports a name that looks like a test or diagnostic hook;
* nothing a player receives names the test builds: not the release file
  list, not a patch manifest;
* each test build exists, carries what its shipped twin exports plus the
  hooks, and is named so it cannot be mistaken for the shipped file;
* the test builds are export-ignore, so not even the release SOURCE zip
  carries them (there, the tests that drive them skip), while a git
  checkout must track every one so CI never skips them;
* the VV3 companion no longer publishes the two world-draw debug buffers it
  used to hand the executable at 0x6E003C / 0x6E0040.
"""
from __future__ import annotations

import re
import struct
import unittest
from pathlib import Path

import pefile

ROOT = Path(__file__).resolve().parents[1]
TEST_DLLS = ROOT / "tests" / "test_dlls"

# A name a test seam or a diagnostic would carry.  Case-insensitive: a
# `DebugDump` and a `debugDump` are the same mistake.
HOOK_NAME = re.compile(r"probe|stats|debug|diag|test", re.IGNORECASE)

# Shipped DLL -> (its test build, its source directory under native/).
TEST_BUILDS = {
    "assets/fix_huts/VVFP Fix Huts.dll": ("VVFP Fix Huts.test.dll", "vvfp_fix_huts"),
    "assets/golden_mushroom/VVFP Golden Mushroom.dll": ("VVFP Golden Mushroom.test.dll", "vvfp_golden_mushroom"),
    "assets/healers_study/VVFP Healers Study.dll": ("VVFP Healers Study.test.dll", "vvfp_healers_study"),
    "assets/lesson_cap/VVFP Lesson Cap.dll": ("VVFP Lesson Cap.test.dll", "vvfp_lesson_cap"),
    "assets/work_first/VVFP Work First.dll": ("VVFP Work First.test.dll", "vvfp_work_first"),
    "assets/pathfinding/VVFP Improved Pathfinding.dll": ("VVFP Improved Pathfinding.test.dll", "vvfp_pathfinding"),
    "assets/watering/VVFP VV1 Watering Builds.dll": ("VVFP VV1 Watering Builds.test.dll", "vv1_watering_builds"),
    "assets/number_keys/VVFP VV1 Number Keys.dll": ("VVFP VV1 Number Keys.test.dll", "vv1_number_keys"),
    "assets/parentage/VVFP VV1 Parentage.dll": ("VVFP VV1 Parentage.test.dll", "vv1_parentage"),
    "assets/sort_by/VVFP VV1 Sort By.dll": ("VVFP VV1 Sort By.test.dll", "vv1_sort_by"),
}

VV3_COMPANION = ROOT / "data" / "candidates" / "VVFP VV3 Safe Upgrades.dll"
VV3_SOURCE = ROOT / "native" / "vv3_full_mastery_candidate" / "vv3_full_mastery_candidate.c"


def _export_table(path: Path) -> list[tuple[str, bool]]:
    """(name or '#ordinal', is_data) for every export of `path`.  Data is an
    export whose address is outside every executable section."""
    pe = pefile.PE(str(path), fast_load=True)
    pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXPORT"]])
    directory = getattr(pe, "DIRECTORY_ENTRY_EXPORT", None)
    table = []
    for symbol in (directory.symbols if directory is not None else []):
        section = pe.get_section_by_rva(symbol.address)
        is_data = section is None or not section.Characteristics & 0x20000000  # IMAGE_SCN_MEM_EXECUTE
        name = symbol.name.decode("ascii") if symbol.name else f"#{symbol.ordinal}"
        table.append((name, is_data))
    return table


def _exports(path: Path) -> list[str]:
    return [name for name, _ in _export_table(path) if not name.startswith("#")]


def _shipped_dlls() -> list[Path]:
    """Every DLL a patch can deploy: all of them under assets/ and data/."""
    found = sorted(p for top in ("assets", "data") for p in (ROOT / top).rglob("*")
                   if p.is_file() and p.suffix.lower() == ".dll")
    return found


def _release_files() -> list[str]:
    """scripts/build_release.py's FILES list: what the patcher zip packs."""
    source = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
    block = source[source.index("FILES = ["):]
    block = block[:block.index("\n]")]
    return re.findall(r'"([^"]+)"', block)


class ShippedDllsExportNoHooks(unittest.TestCase):
    def test_the_sweep_sees_every_shipped_companion(self):
        shipped = {p.relative_to(ROOT).as_posix() for p in _shipped_dlls()}
        # Guard the guard: a sweep that found nothing would pass vacuously.
        self.assertGreaterEqual(len(shipped), 25, shipped)
        released = {f for f in _release_files() if f.lower().endswith(".dll")}
        self.assertTrue(released, "the release file list names no DLL")
        self.assertLessEqual(released, shipped, "a released DLL lives outside assets/ and data/")
        self.assertLessEqual(set(TEST_BUILDS), shipped)

    def test_no_shipped_dll_exports_a_test_or_diagnostic_hook(self):
        for dll in _shipped_dlls():
            with self.subTest(dll=dll.relative_to(ROOT).as_posix()):
                hooks = [name for name in _exports(dll) if HOOK_NAME.search(name)]
                self.assertEqual(hooks, [], f"{dll.name} exports test/diagnostic hooks")

    def test_no_shipped_definition_file_declares_one(self):
        for shipped, (_, native) in TEST_BUILDS.items():
            with self.subTest(dll=shipped):
                definition = (ROOT / "native" / native / f"{native}.def").read_text(encoding="utf-8")
                exports = definition.split("EXPORTS", 1)[1]
                self.assertFalse(HOOK_NAME.search(exports), definition)

    def test_no_shipped_dll_exports_data(self):
        """A counter is exported DATA whatever it is called -- the old
        `VvfpFixHutsFoodBypasses` matched no hook word -- and no companion
        needs to hand the game a variable: every real export is code."""
        for dll in _shipped_dlls():
            with self.subTest(dll=dll.relative_to(ROOT).as_posix()):
                data = [name for name, is_data in _export_table(dll) if is_data]
                self.assertEqual(data, [], f"{dll.name} exports data")

    def test_the_pattern_would_have_caught_the_old_exports(self):
        """The regex is not vacuous: every hook the DLLs used to ship matches,
        and the real exports that merely look close do not."""
        for name in ("VvfpGoldenMushroomProbeSelect", "VvfpGoldenMushroomStats", "VvfpFixHutsProbePick",
                     "VvfpFixHutsStats", "_VvfpWorkFirstProbeSite@20", "Vv1ParentageProbeReset",
                     "VvfpVv1WateringStats", "SomeDebugDump", "DiagnosticsOnly", "RunSelfTest"):
            self.assertRegex(name, HOOK_NAME)
        for name in ("WriteVillageStatistics", "ShowOriginsUpgradeMenuState", "ShowVV5Task9Result",
                     "ConfirmVV5Task9Action", "ShowVV2AppearanceChooser"):
            self.assertNotRegex(name, HOOK_NAME)


class TestBuildsStayOutOfTheRelease(unittest.TestCase):
    def test_the_release_list_names_no_test_build(self):
        for entry in _release_files():
            self.assertNotIn("test_dlls", entry)
            self.assertFalse(entry.lower().endswith(".test.dll"), entry)

    def test_no_manifest_names_a_test_build(self):
        for manifest in sorted((ROOT / "data").rglob("*.json")):
            text = manifest.read_text(encoding="utf-8", errors="replace")
            with self.subTest(manifest=manifest.relative_to(ROOT).as_posix()):
                self.assertNotIn("test_dlls", text)
                self.assertNotIn(".test.dll", text)

    def test_the_source_archive_leaves_the_test_builds_out(self):
        """`git archive` (the release source zip) honours export-ignore, so the
        test builds never reach a release, source or patcher zip."""
        rules = (ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines()
        self.assertIn("/tests/test_dlls export-ignore", rules)
        self.assertIn("/tests/test_dlls/** export-ignore", rules)

    @unittest.skipUnless((ROOT / ".git").exists(), "not a git checkout")
    def test_a_checkout_tracks_every_test_build(self):
        """The emulator tests skip when a test build is absent, which is right
        in the source archive and wrong anywhere else: in a checkout every
        test build must be tracked, so CI can never skip them silently."""
        import subprocess
        tracked = subprocess.run(["git", "-C", str(ROOT), "ls-files", "tests/test_dlls"],
                                 capture_output=True, text=True, check=True).stdout.splitlines()
        self.assertEqual(sorted(Path(t).name for t in tracked),
                         sorted(name for name, _ in TEST_BUILDS.values()))

    @unittest.skipUnless(any(TEST_DLLS.glob("*.test.dll")), "test builds are not in the release source archive (tests/test_dlls)")
    def test_each_test_build_is_the_shipped_dll_plus_its_hooks(self):
        for shipped, (test_name, native) in TEST_BUILDS.items():
            with self.subTest(dll=shipped):
                test_dll = TEST_DLLS / test_name
                self.assertTrue(test_dll.is_file(), f"{test_dll} missing: run scripts/build_*.ps1 for {native}")
                shipped_exports = set(_exports(ROOT / shipped))
                test_table = dict(_export_table(test_dll))
                test_exports = set(test_table)
                self.assertLessEqual(shipped_exports, test_exports, "the test build lost a real export")
                extra = test_exports - shipped_exports
                self.assertTrue(extra, "the test build carries no hook: nothing to test with")
                # Everything the shipped DLL lacks is a hook by name or a
                # counter (exported data), never a real feature entry point.
                self.assertTrue(all(HOOK_NAME.search(n) or test_table[n] for n in extra),
                                f"the test build differs by a non-hook export: {sorted(extra)}")
                test_def = (ROOT / "native" / native / f"{native}_test.def").read_text(encoding="utf-8")
                self.assertIn(f'LIBRARY "{test_name}"', test_def)

    def test_every_build_script_builds_both(self):
        for shipped, (test_name, native) in TEST_BUILDS.items():
            scripts = [p for p in (ROOT / "scripts").glob("build_*.ps1")
                       if f'"{native}.def"' in p.read_text(encoding="utf-8-sig")]
            with self.subTest(dll=shipped):
                self.assertEqual(len(scripts), 1, scripts)
                text = scripts[0].read_text(encoding="utf-8-sig")
                self.assertIn("/DVVFP_TEST", text)
                self.assertIn(f"{native}_test.def", text)
                self.assertIn(f'"{test_name}"', text)
                # the shipped compile comes first and never defines VVFP_TEST
                shipped_block = text[:text.index("/DVVFP_TEST")]
                self.assertIn(f'"{native}.def"', shipped_block)
                self.assertIn(f'"{Path(shipped).name}"', shipped_block)


class Vv3CompanionPublishesNoDebugBuffers(unittest.TestCase):
    def test_the_source_has_no_world_draw_debug_capture(self):
        source = VV3_SOURCE.read_text(encoding="utf-8")
        for needle in ("g_vv3_worlddbg", "g_vv3_chiefdbg", "0x006E003C", "0x006E0040",
                       "VV3_WORLD_POS_FN"):
            self.assertNotIn(needle, source)

    def test_the_shipped_companion_never_writes_those_slots(self):
        data = VV3_COMPANION.read_bytes()
        for slot in (0x6E003C, 0x6E0040):
            self.assertNotIn(struct.pack("<I", slot), data, hex(slot))


if __name__ == "__main__":
    unittest.main()
