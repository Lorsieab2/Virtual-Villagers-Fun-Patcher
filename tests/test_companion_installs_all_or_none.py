"""Every companion installs ALL of its sites, or NONE of them.

The owner (2026-10-24), after a review found a partial-install bug: "I do not
want any half-assed patches.  Fix them please!!!"  Every companion DLL that
writes into the game's code at run time now goes through one writer,
native/shared/install_sites.h: every site checked, every site made writable,
then every site written, every protection restored and the instruction cache
flushed -- and if any VirtualProtect fails, nothing has been written.

This runs each SHIPPED companion (or, for a shared header with no companion
of its own, its test build) in an emulator beside the executable the patcher
renders for its row, and:

* lets the install succeed once, to count its VirtualProtect calls and learn
  the fully installed image;
* then, for EVERY one of those calls in turn, makes that one call fail and
  installs again on a fresh process: no byte of the game's image may be
  written at all (a write that is "put back" afterwards counts -- the memory
  hook sees it), the export reports "not installed", every page's protection
  is what it was, and no page is ever left writable and executable;
* calls the install once more after the failure: the image is then either
  untouched or exactly the fully installed one -- never part of it;
* renders the game's whole public catalog and checks the install still goes
  in, so "all or none" never turns a feature off beside the other rows.

A mutation run against the companions as they were before (their per-site
writes) fails here: tests/test_companion_installs_all_or_none.py with
VVFP_ALL_OR_NONE_DLL_DIR pointing at the old DLLs (see the PR).
"""
from __future__ import annotations

import functools
import os
import struct
import sys
import unittest
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_fun_patcher as patcher  # noqa: E402

try:
    import pefile  # noqa: F401
    from unicorn import UC_HOOK_MEM_WRITE

    from story_emulator import HEAP, RETURN, Process

    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False
    # Stand-ins so the module still defines Machine and the emulator cases
    # skip (_skip_reason) while OneWriterTests run without pefile/unicorn.
    Process = object
    HEAP = RETURN = 0
    UC_HOOK_MEM_WRITE = None

TEST_BUILD_ABSENT = "test builds are not in the release source archive (tests/test_dlls)"
# A mutation run points this at a folder holding older builds of the DLLs.
DLL_DIR = os.environ.get("VVFP_ALL_OR_NONE_DLL_DIR")

PAGE_EXECUTE_READ = 0x20
PAGE_EXECUTE_READWRITE = 0x40
PAGE_READWRITE = 0x04
PAGE = 0x1000
FAKE_MODULE = 0x0C000000


@functools.lru_cache(maxsize=None)
def _builds():
    return {build.id: build for build in patcher.load_builds()}


def stock_path(game: int) -> Path:
    return ROOT / "inputs" / f"vv{game}-stock-copy" / _builds()[f"vv{game}"].input_name


@functools.lru_cache(maxsize=None)
def render(game: int, ids: tuple[str, ...], mode: str) -> bytes:
    data, _ = patcher.render_patched_bytes(stock_path(game), _builds()[f"vv{game}"], mode,
                                           list(ids))
    return bytes(data)


def with_requirements(game: int, rows: list[str]) -> tuple[str, ...]:
    """The rows and everything they require, dependency first."""
    by_id = {p.id: p for p in patcher.load_fun_patches()}
    chosen: list[str] = []

    def add(row: str) -> None:
        if row in chosen:
            return
        for dependency in patcher._dependency_ids(by_id[row]):
            if dependency in by_id:
                add(dependency)
        chosen.append(row)

    for row in rows:
        add(row)
    return tuple(patcher.resolve_fun_patch_ids(chosen, game_id=f"vv{game}"))


@functools.lru_cache(maxsize=None)
def whole_catalog(game: int) -> tuple[str, ...]:
    """Every public row of the game, an alternative row left out (it is never
    built with the row it replaces)."""
    prefix = f"vv{game}_"
    rows = [p for p in patcher.load_public_fun_patches() if p.id.startswith(prefix)]
    chosen = [p.id for p in rows if p.id not in patcher.ALTERNATIVE_FUN_PATCH_IDS]
    return tuple(patcher.resolve_fun_patch_ids(chosen, game_id=f"vv{game}"))


class Machine(Process):
    """The story emulator with what the installers need: tracked page
    protections (VirtualQuery answers from them), one VirtualProtect that can
    be made to fail, VirtualAlloc/VirtualFree, and a hook on every write into
    the game's image."""

    def __init__(self, exe: bytes, dll: Path, *, present: tuple[str, ...] = ()):
        self.fail_protect: int | None = None
        self.protect_calls = 0
        self.protect_log: list[tuple[int, int, int, int, int]] = []   # (index, address, new, writes before, old)
        self.prot: dict[int, int] = {}
        self.image_writes: list[tuple[int, int]] = []
        self.flushed: list[tuple[int, int]] = []
        self.present = present            # patcher DLL names that "exist"
        super().__init__(exe, dll)
        pe = self._exe_pe
        self.exe_base = pe.OPTIONAL_HEADER.ImageBase
        self.exe_size = (pe.OPTIONAL_HEADER.SizeOfImage + PAGE - 1) & ~(PAGE - 1)
        for page in range(self.exe_base, self.exe_base + self.exe_size, PAGE):
            self.prot[page] = PAGE_EXECUTE_READ
        self.mu.hook_add(UC_HOOK_MEM_WRITE, self._on_write, begin=self.exe_base,
                         end=self.exe_base + self.exe_size - 1)

    # ---- memory ---------------------------------------------------------
    def _on_write(self, mu, access, address, size, value, user):
        self.image_writes.append((address, size))

    def image(self) -> bytes:
        return self.read(self.exe_base, self.exe_size)

    def protection(self, address: int) -> int:
        page = address & ~(PAGE - 1)
        if page in self.prot:
            return self.prot[page]
        return PAGE_READWRITE

    def _api_VirtualQuery(self):
        address, buffer, length = self.arg(0), self.arg(1), self.arg(2)
        region = None
        for begin, end, _ in self.mu.mem_regions():
            if begin <= address <= end:
                region = (begin, end)
        if region is None:
            return 0, 12
        page = address & ~(PAGE - 1)
        prot = self.protection(address)
        # The run of pages from here with the same protection, as Windows does.
        end = page
        while end <= region[1] and self.protection(end) == prot:
            end += PAGE
        info = struct.pack("<7I", page, region[0], prot, end - page, 0x1000, prot, 0x1000000)
        self.write(buffer, info[:length])
        return min(length, 28), 12

    def _api_VirtualProtect(self):
        address, size, new, old_out = self.arg(0), self.arg(1), self.arg(2), self.arg(3)
        index = self.protect_calls
        self.protect_calls += 1
        self.protect_log.append((index, address, new, len(self.image_writes), self.protection(address)))
        if index == self.fail_protect:
            return 0, 16
        first = address & ~(PAGE - 1)
        self.put32(old_out, self.protection(address))
        for page in range(first, address + max(size, 1), PAGE):
            self.prot[page] = new
        return 1, 16

    def _api_VirtualAlloc(self):
        size, protect = self.arg(1), self.arg(3)
        at = self.alloc(size)
        for page in range(at, at + size, PAGE):
            self.prot[page] = protect
        return at, 16

    def _api_VirtualFree(self):
        address = self.arg(0)
        for page in [p for p in self.prot if address <= p < address + 0x100000 and p >= HEAP]:
            del self.prot[page]
        return 1, 12

    def _api_FlushInstructionCache(self):
        self.flushed.append((self.arg(1), self.arg(2)))
        return 1, 12

    # A companion another companion needs (Island Events' Parentage Export)
    # "exists" only when the case names it.
    def _api_GetFileAttributesW(self):
        name = self.wstring(self.arg(0))
        return (0x20 if any(name.endswith(p) for p in self.present) else 0xFFFFFFFF), 4

    def _api_LoadLibraryExW(self):
        name = self.wstring(self.arg(0))
        self.loaded.append(name)
        return (FAKE_MODULE if any(name.endswith(p) for p in self.present) else 0), 12

    def _api_LoadLibraryW(self):
        name = self.wstring(self.arg(0))
        self.loaded.append(name)
        return (FAKE_MODULE if any(name.endswith(p) for p in self.present) else 0), 4

    def _api_GetProcAddress(self):
        return (RETURN if self.arg(0) == FAKE_MODULE else 0), 8

    def _api_GetModuleHandleW(self):
        return 0, 4

    def _api_InitializeCriticalSection(self):
        return 0, 4

    def _api_EnterCriticalSection(self):
        return 0, 4

    def _api_LeaveCriticalSection(self):
        return 0, 4

    def _api_CreateFileW(self):
        return 0xFFFFFFFF, 28                    # INVALID_HANDLE_VALUE: nothing on disk

    def _api_CreateFileA(self):
        return 0xFFFFFFFF, 28

    def _api_CreateDirectoryW(self):
        return 0, 8

    def _api_CreateDirectoryA(self):
        return 0, 8

    def _api_GetLocalTime(self):
        self.write(self.arg(0), bytes(16))
        return 0, 4

    def _api_GetTickCount(self):
        return 1000, 0

    def _api_QueryPerformanceFrequency(self):
        self.write(self.arg(0), struct.pack("<Q", 1000000))
        return 1, 4

    def _api_QueryPerformanceCounter(self):
        self.write(self.arg(0), struct.pack("<Q", 1))
        return 1, 4

    # ---- checks ---------------------------------------------------------
    def wx_pages(self) -> list[int]:
        return sorted(p for p, prot in self.prot.items() if prot == PAGE_EXECUTE_READWRITE)

    def changed_protections(self) -> list[int]:
        return sorted(p for p in range(self.exe_base, self.exe_base + self.exe_size, PAGE)
                      if self.prot.get(p) != PAGE_EXECUTE_READ)


@dataclass
class Case:
    name: str
    dll: str                                   # relative to ROOT
    games: tuple[int, ...]
    rows: Callable[[int], list[str]]
    call: Callable[[Machine, int], int]
    reports: bool = True                       # the export returns whether it is installed
    mode: str = "collection_progression"
    present: tuple[str, ...] = ()
    test_build: bool = False

    def dll_path(self) -> Path:
        if DLL_DIR:
            return Path(DLL_DIR) / Path(self.dll).name
        return ROOT / self.dll


def _startup(m: Machine, game: int) -> int:
    return m.export("VvfpStartup", game, 0)


def _with_origins(*rows: str):
    return lambda g: [f"vv{g}_origins_village_wide_upgrades"] + [r.format(g=g) for r in rows]


CASES = [
    Case("VV1 Easier Healing", "assets/easier_healing/VVFP VV1 Easier Healing.dll", (1,),
         lambda g: ["vv1_easier_healing_mastery"], _startup, reports=False),
    Case("VV1 Research At Max", "assets/research_at_max/VVFP VV1 Research At Max.dll", (1,),
         lambda g: ["vv1_continue_research_at_max_technologies"], _startup, reports=False),
    Case("VV1 Watering Builds", "assets/watering/VVFP VV1 Watering Builds.dll", (1,),
         lambda g: ["vv1_watering_trains_building"],
         lambda m, g: m.export("VvfpVv1WateringBuildsInstall")),
    Case("Cause of Death", "assets/cause_of_death/VVFP Cause of Death.dll", (1, 2, 3, 4, 5),
         lambda g: [f"vv{g}_cause_of_death"], lambda m, g: m.export("VvfpCauseInstall", g, 0)),
    Case("VV3 Chief Hospital", "assets/chief_hospital/VVFP VV3 Chief Hospital.dll", (3,),
         lambda g: ["vv3_chief_hospital_supervision"], _startup, reports=False),
    Case("Fix Huts", "assets/fix_huts/VVFP Fix Huts.dll", (1, 2, 4, 5),
         lambda g: [f"vv{g}_builders_fix_huts"], lambda m, g: m.export("VvfpFixHutsInstall", g)),
    Case("Game Log", "assets/game_log/VVFP Game Log.dll", (1, 2, 3, 4, 5),
         lambda g: [f"vv{g}_game_log"], _startup, reports=False),
    Case("Golden Mushroom", "assets/golden_mushroom/VVFP Golden Mushroom.dll", (1, 3, 4, 5),
         lambda g: [f"vv{g}_super_secret_golden_mushroom"],
         lambda m, g: m.export(f"VvfpGoldenMushroomVv{g}")),
    Case("Healers Study", "assets/healers_study/VVFP Healers Study.dll", (1, 2),
         lambda g: [f"vv{g}_healers_study_regardless_of_food"],
         lambda m, g: m.export("VvfpHealersStudyInstall", g)),
    Case("Island Events", "assets/island_events/VVFP Island Events.dll", (1, 2, 3, 4, 5),
         lambda g: [f"vv{g}_island_events"], _startup, reports=False,
         present=("VVFP Parentage Export.dll",)),
    Case("Last Names", "assets/last_names/VVFP Last Names.dll", (1, 2, 3, 4, 5),
         lambda g: [f"vv{g}_last_names"], _startup, reports=False),
    Case("Lesson Cap", "assets/lesson_cap/VVFP Lesson Cap.dll", (1, 2),
         lambda g: ["vv1_school_lessons_cap_50" if g == 1 else "vv2_teaching_children_cap_50"],
         lambda m, g: m.export("VvfpLessonCapInstall", g)),
    Case("Improved Pathfinding", "assets/pathfinding/VVFP Improved Pathfinding.dll", (1, 2),
         lambda g: [f"vv{g}_improved_pathfinding"], lambda m, g: m.export("VvfpPathfindingInstall", g)),
    Case("Story Upgrades", "assets/story_upgrades/VVFP Story Upgrades.dll", (1, 2, 3, 4, 5),
         _with_origins("vv{g}_story_cheat_upgrades"), lambda m, g: m.export("VvfpStoryArm", g)),
    Case("Storytelling", "assets/storytelling/VVFP Storytelling.dll", (1, 2),
         lambda g: [f"vv{g}_storytelling"], _startup, reports=False),
    Case("VV2 Totems", "assets/vv2_totems/VVFP VV2 Totems.dll", (2,),
         lambda g: ["vv2_totems_out_of_entries"], _startup, reports=False),
    Case("VV3 Both Factions", "assets/both_factions/VVFP VV3 Both Factions.dll", (3,),
         lambda g: ["vv3_both_factions"], _startup, reports=False),
    Case("VV3 Trees Refill Together", "assets/fruit_trees/VVFP VV3 Trees Refill Together.dll", (3,),
         lambda g: ["vv3_fruit_trees_refill_together"], _startup, reports=False),
    Case("VV3 Trees Take Turns", "assets/fruit_trees/VVFP VV3 Trees Take Turns.dll", (3,),
         lambda g: ["vv3_fruit_trees_take_turns"], _startup, reports=False),
    Case("Speed Change Timers", "assets/speed_timers/VVFP Speed Change Timers.dll", (3, 4),
         lambda g: [f"vv{g}_fix_vanilla_bugs"], _startup, reports=False),
    # A New Home's Fix Vanilla Bugs: the Golden Child and island events (started by the Speed
    # Change Timers companion the row ships with it).
    Case("VV1 Golden Child Safe", "assets/golden_child_safe/VVFP VV1 Golden Child Safe.dll", (1,),
         lambda g: ["vv1_fix_vanilla_bugs"],
         lambda m, g: (m.export("VvfpStartup", g, 0), m.export("VvfpGoldenChildSafeInstalled"))[1]),
    # Fix Vanilla Bugs (The Lost Children, The Tree of Life, New Believers): the last head and body rows.
    Case("Appearance Rolls", "assets/appearance_rolls/VVFP Appearance Rolls.dll", (2, 4, 5),
         lambda g: [f"vv{g}_fix_vanilla_bugs"],
         lambda m, g: (m.export("VvfpStartup", g, 0), m.export("VvfpAppearanceRollsInstalled"))[1]),
    Case("Difficulty Settings", "assets/difficulty/VVFP Difficulty.dll", (4, 5),
         lambda g: [f"vv{g}_difficulty_settings"], _startup, reports=False),
    Case("VV1 Genetics", "assets/genetics/VVFP VV1 Genetics.dll", (1,),
         lambda g: ["vv1_genetics"], _startup, reports=False),
    # Grey Hair at 55 (A New Home): the 29 head-sheet reads and the two engine draws.
    Case("VV1 Grey Hair", "assets/vv1_grey_hair/VVFP VV1 Grey Hair.dll", (1,),
         lambda g: ["vv1_grey_hair"],
         lambda m, g: (m.export("VvfpStartup", g, 0), m.export("VvfpGreyHairInstalled"))[1]),
    # Change Appearance's head look (every game's Origins row): the age compares the old heads hang on.
    Case("Head Look", "assets/head_look/VVFP Head Look.dll", (2, 3, 4, 5),
         lambda g: [f"vv{g}_enable_origins_exclusive_features"],
         lambda m, g: (m.export("VvfpStartup", g, 0), m.export("VvfpHeadLookInstalled", g))[1]),
    Case("Work First", "assets/work_first/VVFP Work First.dll", (1, 2, 4, 5),
         lambda g: [f"vv{g}_builders_and_healers_work_first"],
         lambda m, g: m.export("VvfpWorkFirstInstall", g)),
    # The Origins companions' island-timer keeper (native/shared/
    # island_timer_keep.h) through its own test build, which carries the
    # same header and every game's sites.
    Case("Island Event Timer (Origins companions)", "tests/test_dlls/VVFP Island Event Timer.test.dll",
         (1, 2, 3, 4, 5), _with_origins("vv{g}_story_cheat_upgrades"),
         lambda m, g: m.export("ItkProbeInstall", g), test_build=True),
]


def _skip_reason(case: Case, game: int) -> str | None:
    if not HAVE_EMULATOR:
        return "unicorn/pefile not installed"
    if not stock_path(game).is_file():
        return "stock executable not present (inputs/)"
    if not case.dll_path().is_file():
        return TEST_BUILD_ABSENT if case.test_build else f"{case.dll} missing"
    return None


class AllOrNoneTests(unittest.TestCase):
    maxDiff = None

    def machine(self, case: Case, game: int, exe: bytes) -> Machine:
        return Machine(exe, case.dll_path(), present=case.present)

    def check_clean(self, m: Machine, what: str) -> None:
        self.assertEqual(m.changed_protections(), [], f"{what}: a game page kept a changed protection")
        self.assertEqual(m.wx_pages(), [], f"{what}: a page is writable and executable")

    def run_case(self, case: Case) -> None:
        ran = False
        for game in case.games:
            reason = _skip_reason(case, game)
            if reason:
                continue
            ran = True
            # The row with what it requires (Work First needs Fix Huts, ...).
            ids = with_requirements(game, case.rows(game))
            exe = render(game, ids, case.mode)
            with self.subTest(companion=case.name, game=game):
                # 1. The install goes in: every site, protections back, cache flushed.
                m = self.machine(case, game, exe)
                stock = m.image()
                result = case.call(m, game)
                installed = m.image()
                calls = m.protect_calls
                if case.reports:
                    self.assertEqual(result, 1, "the install goes in on the row's own executable")
                self.assertNotEqual(installed, stock, "the install writes its sites")
                self.check_clean(m, "installed")
                changed = [i for i in range(len(stock)) if stock[i] != installed[i]]
                for offset in changed:
                    va = m.exe_base + offset
                    self.assertTrue(any(a <= va < a + n for a, n in m.flushed),
                                    f"0x{va:X} written but its instruction cache never flushed")
                self.assertGreater(calls, 0)
                in_image = range(m.exe_base, m.exe_base + m.exe_size)
                late_unlocks = [(i, hex(a)) for i, a, new, before, old in m.protect_log
                                if a in in_image and new == PAGE_EXECUTE_READWRITE
                                and old != PAGE_EXECUTE_READWRITE and before > 0]
                self.assertEqual(late_unlocks, [],
                                 "a site was made writable after another was already written")
                # Every call that can still refuse the install: each one made
                # before the first byte of the game is written (after that
                # come only the restores of what was unlocked).
                failable = [i for i, _, _, before, _ in m.protect_log if before == 0]
                self.assertTrue(failable)
                # 2. Each of them in turn refused: nothing written at all.
                for k in failable:
                    m = self.machine(case, game, exe)
                    m.fail_protect = k
                    result = case.call(m, game)
                    with self.subTest(failing_virtualprotect=k):
                        self.assertEqual(m.image_writes, [],
                                         "a site was written (even if put back) although the install failed")
                        self.assertEqual(m.image(), stock, "the game's code is untouched")
                        if case.reports:
                            self.assertEqual(result, 0, "the install reports itself not installed")
                        self.check_clean(m, f"VirtualProtect #{k} refused")
                        # 3. Asked again: all of it or none of it, never part.
                        case.call(m, game)
                        again = m.image()
                        self.assertIn(again, (stock, installed), "a later call left the feature in part")
                        self.check_clean(m, "asked again")
        if not ran:
            self.skipTest(_skip_reason(case, case.games[0]) or "nothing to run")

    def run_catalog(self, case: Case) -> None:
        ran = False
        for game in case.games:
            if _skip_reason(case, game):
                continue
            own = case.rows(game)
            by_id = {p.id: p for p in patcher.load_public_fun_patches()}
            conflicts = {c for r in own if r in by_id for c in patcher.conflict_ids(by_id[r])}
            chosen = [i for i in whole_catalog(game) if i not in conflicts] + own
            ids = tuple(patcher.resolve_fun_patch_ids(list(dict.fromkeys(chosen)), game_id=f"vv{game}"))
            ran = True
            with self.subTest(companion=case.name, game=game):
                exe = render(game, ids, case.mode)
                m = self.machine(case, game, exe)
                stock = m.image()
                result = case.call(m, game)
                if case.reports:
                    self.assertEqual(result, 1, "with every other row, the install still goes in")
                self.assertNotEqual(m.image(), stock, "with every other row, the install still writes its sites")
                self.check_clean(m, "whole catalog")
        if not ran:
            self.skipTest(_skip_reason(case, case.games[0]) or "nothing to run")


def _add(case: Case) -> None:
    slug = "".join(c if c.isalnum() else "_" for c in case.name.lower()).strip("_")
    setattr(AllOrNoneTests, f"test_{slug}_installs_every_site_or_none",
            lambda self, c=case: self.run_case(c))
    setattr(AllOrNoneTests, f"test_{slug}_installs_beside_the_whole_catalog",
            lambda self, c=case: self.run_catalog(c))


for _case in CASES:
    _add(_case)


class OneWriterTests(unittest.TestCase):
    """No companion writes the game's code except through the shared writer."""

    def test_every_runtime_writer_uses_install_sites(self):
        native = ROOT / "native"
        offenders = []
        for path in sorted(native.rglob("*")):
            if path.suffix not in {".c", ".h", ".inc"} or "harness" in path.name or path.name == "install_sites.h":
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if "PAGE_EXECUTE_READWRITE, &" in text:
                offenders.append(str(path.relative_to(ROOT)))
        # VV1 Number Keys is fixed in its own PR (#607).
        offenders = [o for o in offenders if "vv1_number_keys" not in o]
        self.assertEqual(offenders, [], "a companion unlocks game code outside native/shared/install_sites.h")

    def test_the_writer_unlocks_every_site_before_writing_any(self):
        text = (ROOT / "native" / "shared" / "install_sites.h").read_text(encoding="utf-8")
        body = text[text.index("static int vvfp_install_sites("):]
        body = body[:body.index("\n}\n")]
        unlock = body.index("PAGE_EXECUTE_READWRITE")
        write = body.index("memcpy(")
        self.assertLess(body.index("vvfp_site_holds("), unlock, "every site is checked first")
        self.assertLess(unlock, write, "every site is made writable before any is written")
        self.assertIn("for (i = count; i-- > 0;)", body, "protections are restored last first")
        self.assertIn("FlushInstructionCache(", body)


if __name__ == "__main__":
    unittest.main()
