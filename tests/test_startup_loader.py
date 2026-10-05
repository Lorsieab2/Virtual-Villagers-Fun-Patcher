"""Every patcher companion is loaded and armed when the game opens.

The owner: "All patcher add-ons must start as soon as the game is opened, as
early as possible" -- for every game, build, population mode and patch
combination.  The games catch up the time that passed while they were closed
when a village loads (and after a Time Warp), and most births, deaths,
burials, disappearances and island events happen in that batch; a companion
armed later than that never saw them live.  Measured before this change: The
Secret City installed Cause of Death and Story / Cheat Upgrades only when a
villager was first drawn or the Origins menu opened -- after the catch-up --
and every other game installed its runtime companions from the first frame,
the village constructor or the slot load: before the catch-up, but not at
game open.

Now every published build that ships a companion DLL also ships
"VVFP Startup.dll" and an appended `.vvfpst` section whose stub replaces the
C runtime's `call WinMain` (src/vv_fun_patcher.py, _apply_startup_loader).

Every test here EMULATES the executable the patcher publishes (render plus
the published-build finalizers) from that very call to the first instruction
of WinMain, with the shipped companion DLLs mapped from their own files as
the stub and the companions load them (tests/startup_emulation.py).  Nothing
of the game has run at that point, so whatever is armed when WinMain is
entered is armed before the title screen, the slot menu, every load and the
load-time catch-up, which only WinMain's own loop ever reaches.

Pinned, for every game x population mode x selection (each public patch
that ships a DLL, alone with its prerequisites; every public patch; every
public patch with 256 Villagers (Experimental)):

* WinMain is entered with the C runtime's stack, arguments and registers;
* every shipped DLL is loaded, each by its full path in the game folder;
* every runtime detour each selected row declares (`runtime_detours`) is
  written before WinMain -- and, the mutation, none is when the loader is
  left out (the old late install points);
* nothing of the game's own writable data is read or written and no game
  routine runs; every byte a companion writes was read (verified) first;
* a missing companion never stops the others or the game.
"""
from __future__ import annotations

import re
import struct
import sys
import unittest
from functools import lru_cache
from pathlib import Path

import pefile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_fun_patcher as vfp  # noqa: E402
from startup_emulation import StartupMachine  # noqa: E402

STOCK_DIR = ROOT / "research" / "stock-executables"
GAMES = ("vv1", "vv2", "vv3", "vv4", "vv5")
MODES = ("stock", "collection_progression", "immediate_fixed")
POPULATION_256 = {"vv3_population_256", "vv4_population_256", "vv5_population_256"}


@lru_cache(maxsize=None)
def build_of(game: str):
    return next(b for b in vfp.load_builds() if b.id == game)


def stock_path(game: str) -> Path:
    return STOCK_DIR / build_of(game).input_name


STOCK_PRESENT = all(stock_path(g).is_file() for g in GAMES)
STOCK_ABSENT = "the stock executables are not in this checkout (research/stock-executables)"


@lru_cache(maxsize=None)
def catalog() -> dict:
    return {p.id: p for p in vfp.load_fun_patches()}


def public_ids(game: str) -> list[str]:
    out = []
    for p in vfp.load_fun_patches():
        r = p.raw
        if p.game_id == game and not r.get("catalog_hidden") and r.get("catalog_enabled", True) \
                and r.get("enabled", True):
            out.append(p.id)
    return out


def closure(feature_id: str, into: list[str] | None = None) -> list[str]:
    """`feature_id` and everything it requires, prerequisites first."""
    into = [] if into is None else into
    for dependency in catalog()[feature_id].raw.get("dependencies") or []:
        closure(dependency, into)
    if feature_id not in into:
        into.append(feature_id)
    return into


def ships_dll(feature_id: str) -> bool:
    return any(str(item.get("destination", "")).lower().endswith(".dll")
               for item in catalog()[feature_id].raw.get("companion_files", []))


def selections(game: str) -> dict[str, list[str]]:
    """Every selection that changes which companions are installed: each
    public DLL row alone (with its prerequisites), everything, and
    everything with 256 Villagers (Experimental)."""
    ids = public_ids(game)
    out = {f"only {i}": closure(i) for i in ids if ships_dll(i)}
    out["every public patch"] = [i for i in ids if i not in POPULATION_256]
    if any(i in POPULATION_256 for i in ids):
        out["every public patch + 256"] = ids
    return out


@lru_cache(maxsize=None)
def published(game: str, mode: str, selection: tuple[str, ...], loader: bool = True):
    """The executable as the patcher publishes it, and the files beside it.
    loader=False: everything but the startup loader -- the old builds."""
    build = build_of(game)
    data, applied = vfp.render_patched_bytes(stock_path(game), build, mode, list(selection))
    features = vfp._attach_automatic_companions(game, vfp._selected_fun_patches(build, list(selection)))
    if loader:
        vfp._finalize_published_bytes(data, build, features, applied)
    elif game not in vfp.NAME_CRASH_IMMUNITY_EXEMPT_BUILD_IDS:
        vfp._require_name_crash_immunity(data, build.input_name, applied)
    shipped = {}
    for feature in features:
        for item in feature.raw.get("companion_files", []):
            if str(item["destination"]).lower().endswith(".dll"):
                if not loader and item["destination"] == vfp.STARTUP_LOADER_DLL:
                    continue
                shipped[item["destination"]] = ROOT / item["source"]
    return bytes(data), shipped, tuple(f.id for f in features)


def declared_detours(feature_ids) -> list[tuple[int, bytes, str]]:
    out = []
    for feature_id in feature_ids:
        for detour in catalog()[feature_id].raw.get("runtime_detours", []) or []:
            out.append((int(str(detour["va"]), 0), bytes.fromhex(detour["stock_bytes"]),
                        f"{feature_id} {detour.get('routine', '')[:60]}"))
    return out


def run(game: str, mode: str, selection, loader: bool = True, drop=()):
    exe, shipped, features = published(game, mode, tuple(selection), loader)
    shipped = {k: v for k, v in shipped.items() if k not in drop}
    machine = StartupMachine(exe, build_of(game).input_name, shipped)
    call_va, winmain = vfp.STARTUP_LOADER_WINMAIN_CALL[game]
    before = {va: machine.code(va, len(stock)) for va, stock, _ in declared_detours(features)}
    result = machine.run_to_winmain(call_va, winmain)
    return machine, result, features, before, shipped


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
class StartupLoaderPlacement(unittest.TestCase):

    def test_the_call_sites_are_the_c_runtimes_call_of_winmain(self):
        # VV1-VV3 (MSVC 7.1 CRT): push nShowCmd; push lpCmdLine; push esi(0);
        # push esi(0); call edi (GetModuleHandleA(NULL)); push eax; call WinMain.
        # VV4-VV5 (MSVC 8 CRT): push ecx; push eax; push 0; push 0x400000; call.
        prefixes = {
            "vv1": "50FF759856 56FFD750", "vv2": "50FF759856 56FFD750", "vv3": "50FF759856 56FFD750",
            "vv4": "51506A006800004000", "vv5": "51506A006800004000",
        }
        for game in GAMES:
            with self.subTest(game=game):
                call_va, winmain = vfp.STARTUP_LOADER_WINMAIN_CALL[game]
                pe = pefile.PE(str(stock_path(game)), fast_load=True)
                data = stock_path(game).read_bytes()
                at = pe.get_offset_from_rva(call_va - 0x400000)
                self.assertEqual(data[at:at + 5], b"\xE8" + struct.pack("<i", winmain - (call_va + 5)))
                prefix = bytes.fromhex(prefixes[game].replace(" ", ""))
                self.assertEqual(data[at - len(prefix):at], prefix)
                # The only call of WinMain in the executable.
                calls = [m.start() for m in re.finditer(b"\xE8", data)
                         if m.start() + 5 <= len(data)
                         and struct.unpack_from("<i", data, m.start() + 1)[0]
                         == winmain - (0x400000 + pe.get_rva_from_offset(m.start()) + 5)]
                self.assertEqual(calls, [at])

    def test_a_build_without_a_companion_dll_is_left_alone(self):
        for game in GAMES:
            selection = [i for i in public_ids(game) if not ships_dll(i) and not catalog()[i].raw.get("dependencies")
                         and i not in POPULATION_256][:3]
            with self.subTest(game=game, selection=selection):
                features = vfp._attach_automatic_companions(game, vfp._selected_fun_patches(build_of(game), selection))
                if any(ships_dll(f.id) or f.raw.get("_start_over_reset_carrier") for f in features):
                    continue
                exe, shipped, _ = published(game, "collection_progression", tuple(selection))
                self.assertNotIn(b".vvfpst", [s.Name.rstrip(b"\0") for s in pefile.PE(data=exe, fast_load=True).sections])
                self.assertNotIn(vfp.STARTUP_LOADER_DLL, shipped)

    def test_the_stub_is_the_template_at_its_own_address(self):
        for game in GAMES:
            with self.subTest(game=game):
                exe, shipped, _ = published(game, "collection_progression",
                                            tuple(i for i in public_ids(game) if i not in POPULATION_256))
                self.assertIn(vfp.STARTUP_LOADER_DLL, shipped)
                pe = pefile.PE(data=exe)
                section = pe.sections[-1]
                self.assertEqual(section.Name.rstrip(b"\0"), vfp.STARTUP_LOADER_SECTION)
                self.assertEqual(section.Characteristics, 0x60000020)          # R-X, never writable
                self.assertEqual(pe.OPTIONAL_HEADER.CheckSum, pe.generate_checksum())
                va = 0x400000 + section.VirtualAddress
                call_va, winmain = vfp.STARTUP_LOADER_WINMAIN_CALL[game]
                slots = {i.name: i.address for e in pe.DIRECTORY_ENTRY_IMPORT for i in e.imports if i.name}
                features = vfp._attach_automatic_companions(game, vfp._selected_fun_patches(
                    build_of(game), [i for i in public_ids(game) if i not in POPULATION_256]))
                mask = vfp._startup_loader_mask(game, features)
                self.assertEqual(bin(mask).count("1"), len(shipped) - 1)    # all but the loader
                block = vfp._startup_loader_block(va, int(game[2]), mask, slots[b"GetModuleHandleA"],
                                                  slots[b"GetProcAddress"], winmain)
                self.assertEqual(pe.get_data(section.VirtualAddress, len(block)), block)
                self.assertEqual(pe.get_data(call_va - 0x400000, 5),
                                 b"\xE8" + struct.pack("<i", va + vfp.STARTUP_LOADER_CODE_OFFSET - (call_va + 5)))

    def test_every_companion_dll_is_one_the_loader_knows(self):
        source = (ROOT / "native" / "vvfp_startup" / "vvfp_startup.c").read_text(encoding="utf-8")
        source += (ROOT / "native" / "shared" / "startup_companions.h").read_text(encoding="utf-8")
        named = set(re.findall(r'"(VVFP [^"]+\.dll)"', source))
        shipped = {str(item["destination"]) for p in vfp.load_fun_patches()
                   for item in p.raw.get("companion_files", [])
                   if str(item.get("destination", "")).lower().endswith(".dll")}
        self.assertEqual(shipped - named, set())

    def test_the_loader_and_the_patcher_number_the_companions_alike(self):
        header = (ROOT / "native" / "shared" / "startup_companions.h").read_text(encoding="utf-8")
        body = header[header.index("VVFP_STARTUP_COMPANIONS[] = {"):]
        body = body[:body.index("};")]
        self.assertEqual(tuple(re.findall(r'"([^"]+)"', body)), vfp.STARTUP_LOADER_COMPANIONS)
        source = (ROOT / "native" / "vvfp_startup" / "vvfp_startup.c").read_text(encoding="utf-8")
        origins = source[source.index("ORIGINS[VVFP_STARTUP_GAMES + 1] = {"):]
        origins = re.findall(r'"([^"]+)"', origins[:origins.index("};")])
        self.assertEqual(origins, [vfp.STARTUP_LOADER_ORIGINS[g] for g in GAMES])
        self.assertLess(len(vfp.STARTUP_LOADER_COMPANIONS), 31)

    def test_every_origins_companion_exports_vvfpstartup(self):
        for game in GAMES:
            item = next(i for i in catalog()[f"{game}_enable_origins_exclusive_features"].raw.get(
                "companion_files", []) if i["destination"].endswith(".dll") and "Origins" in i["destination"]) \
                if game != "vv5" else None
            path = ROOT / item["source"] if item else ROOT / "data" / "candidates" / "VVFP VV5 Task9 Origins Icons.dll"
            with self.subTest(game=game):
                self.assertIn(b"VvfpStartup", vfp._pe_export_names(path.read_bytes()))
        self.assertIn(b"VvfpStartup", vfp._pe_export_names((ROOT / "assets" / "startup" / "VVFP Startup.dll").read_bytes()))


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
class EveryCompanionArmsBeforeWinMain(unittest.TestCase):

    def check(self, game, mode, name, selection):
        machine, result, features, before, shipped = run(game, mode, selection)
        self.assertEqual(result["esp_at_winmain"], result["esp_before_call"] - 4)
        self.assertEqual(result["return_address"], vfp.STARTUP_LOADER_WINMAIN_CALL[game][0] + 5)
        self.assertEqual(result["arguments"], result["expected_arguments"])
        self.assertEqual(result["registers_at_winmain"], result["registers_before"])
        loads = [c for c in machine.calls if c[0].startswith("LoadLibrary")]
        self.assertTrue(all(full for _, _, full in loads), f"a load not by its full path: {loads}")
        # Every load is wide, by its full path in the patcher's folder; the
        # ANSI API (which turns characters outside the code page into '?')
        # is never used to find a companion.
        self.assertEqual([c for c in loads if c[0] != "LoadLibraryExW"], [])
        self.assertNotIn("GetModuleFileNameA", [c[0] for c in machine.calls])
        self.assertEqual({m.name.lower() for m in machine.modules.values()},
                         {n.lower() for n in shipped})
        armed = 0
        for va, stock, what in declared_detours(features):
            if before[va] != stock:
                # Another selected row owns these bytes in the executable and
                # the companion composes with them (e.g. A New Home's 400-food
                # gate under Builder Action Fixes): its own text says how.
                continue
            armed += 1
            self.assertNotEqual(machine.code(va, len(stock)), stock,
                                f"{what}: 0x{va:X} not armed when WinMain is entered")
        if declared_detours(features):
            self.assertGreater(armed, 0)
        audit = machine.audit(stock_path(game).read_bytes(), vfp.STARTUP_LOADER_WINMAIN_CALL[game][1])
        call_va = vfp.STARTUP_LOADER_WINMAIN_CALL[game][0]
        audit["game_code_run"] = [a for a in audit["game_code_run"] if a[1] != f"{call_va:#x}"]
        for key in ("game_data", "game_code_run", "unverified_writes", "writable_data"):
            self.assertEqual(audit[key], [], f"{key}: {audit[key][:5]}")

    def test_every_build_and_selection(self):
        for game in GAMES:
            for mode in MODES:
                for name, selection in selections(game).items():
                    with self.subTest(game=game, mode=mode, selection=name):
                        self.check(game, mode, name, selection)


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
class TheLateInstallIsNotEnough(unittest.TestCase):
    """The mutation: the same builds without the startup loader -- the
    companions left to their old late install points -- reach WinMain with
    every runtime detour still stock, so the check above would fail."""

    def test_without_the_loader_nothing_is_armed_at_winmain(self):
        for game in GAMES:
            selection = [i for i in public_ids(game) if i not in POPULATION_256]
            with self.subTest(game=game):
                machine, result, features, before, _ = run(game, "collection_progression", selection, loader=False)
                detours = declared_detours(features)
                self.assertTrue(detours)
                self.assertEqual(machine.modules, {})
                for va, stock, what in detours:
                    if before[va] == stock:
                        self.assertEqual(machine.code(va, len(stock)), stock, what)


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
class AMissingCompanionNeverStopsTheGame(unittest.TestCase):

    def test_each_companion_missing_in_turn(self):
        for game in GAMES:
            selection = tuple(i for i in public_ids(game) if i not in POPULATION_256)
            _, shipped, _ = published(game, "collection_progression", selection)
            for missing in sorted(shipped):
                with self.subTest(game=game, missing=missing):
                    machine, result, features, _, present = run(game, "collection_progression", selection,
                                                                 drop=(missing,))
                    self.assertEqual(result["registers_at_winmain"], result["registers_before"])
                    loaded = {m.name for m in machine.modules.values()}
                    if missing == vfp.STARTUP_LOADER_DLL:
                        self.assertEqual(loaded, set())
                    else:
                        self.assertEqual(loaded, set(present))


STALE = {
    "VVFP Fix Huts.dll": "assets/fix_huts/VVFP Fix Huts.dll",
    "VVFP Work First.dll": "assets/work_first/VVFP Work First.dll",
    "VVFP Cause of Death.dll": "assets/cause_of_death/VVFP Cause of Death.dll",
    "VVFP Story Upgrades.dll": "assets/story_upgrades/VVFP Story Upgrades.dll",
    "VVFP Improved Pathfinding.dll": "assets/pathfinding/VVFP Improved Pathfinding.dll",
    "VVFP Lesson Cap.dll": "assets/lesson_cap/VVFP Lesson Cap.dll",
    "VVFP Healers Study.dll": "assets/healers_study/VVFP Healers Study.dll",
}
ORIGINS_SOURCE = {
    "vv1": "assets/origins/VVFP VV1 Origins Icons.dll",
    "vv2": "assets/origins/VVFP VV2 Origins Icons.dll",
    "vv3": "data/candidates/VVFP VV3 Safe Upgrades.dll",
    "vv4": "assets/origins/VVFP VV4 Origins Icons.dll",
    "vv5": "data/candidates/VVFP VV5 Task9 Origins Icons.dll",
}


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
class OnlyThisBuildsCompanions(unittest.TestCase):
    """Codex (#537): a patcher DLL in the folder that this build does not ship
    -- copied along with the game folder, or left by another build -- is
    never loaded: not by VVFP Startup.dll, and not by the Origins companion's
    install bridges, which are handed the same bits.  So it can never install
    a patch nobody selected."""

    def run_with_stale(self, game, selection, stale):
        exe, shipped, features = published(game, "collection_progression", tuple(selection))
        folder = dict(shipped, **{name: ROOT / source for name, source in stale.items()})
        machine = StartupMachine(exe, build_of(game).input_name, folder)
        call_va, winmain = vfp.STARTUP_LOADER_WINMAIN_CALL[game]
        machine.run_to_winmain(call_va, winmain)
        return machine, shipped

    def test_without_origins_no_stale_dll_is_loaded(self):
        for game in ("vv1", "vv3"):
            with self.subTest(game=game):
                stale = dict(STALE, **{vfp.STARTUP_LOADER_ORIGINS[game]: ORIGINS_SOURCE[game]})
                machine, shipped = self.run_with_stale(game, (f"{game}_write_village_statistics",), stale)
                self.assertEqual({m.name for m in machine.modules.values()}, set(shipped))
                self.assertNotIn("VirtualProtect", [c[0] for c in machine.calls])

    def test_with_origins_its_bridges_load_only_this_builds_companions(self):
        # The reviewer's case: Origins shipped, Cause of Death, Story and the
        # rest left in the folder by another build.  Before the bits reached
        # the bridges, VV1 made 227 and VV4 171 VirtualProtect calls for them.
        for game in GAMES:
            with self.subTest(game=game):
                selection = (f"{game}_enable_origins_exclusive_features", f"{game}_write_village_statistics")
                stale = {n: s for n, s in STALE.items()}
                machine, shipped = self.run_with_stale(game, selection, stale)
                self.assertEqual({m.name for m in machine.modules.values()}, set(shipped))
                self.assertNotIn("VirtualProtect", [c[0] for c in machine.calls])


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
class PublicationRemovesUnselectedCompanions(unittest.TestCase):
    """Codex (#537): the output folder starts as a copy of the chosen game
    folder, so a patcher companion already in it stayed in the build and
    switched its patch on.  Publication now removes every file the patcher
    ships for this game that the selection does not ship -- only those."""

    def seed(self, folder: Path, game: str) -> dict[str, bytes]:
        """Every companion file of the game's catalog, plus the loader, plus
        files of the player's own."""
        seeded = {}
        for feature in vfp._load_fun_patch_records():
            if feature.raw.get("game_id") != game:
                continue
            for item in feature.raw.get("companion_files", []):
                source, temp = vfp._vv4_generated_companion_path(item)
                try:
                    if not source.is_file():
                        continue
                    target = folder / vfp._safe_companion_destination(item["destination"])
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if item.get("preimage_sha256"):
                        continue          # a replaced game file: leave the game's own
                    target.write_bytes(source.read_bytes())
                    seeded[target.relative_to(folder).as_posix()] = target.read_bytes()
                finally:
                    if temp is not None:
                        temp.cleanup()
        loader = folder / vfp._safe_companion_destination(vfp.STARTUP_LOADER_DLL)
        loader.parent.mkdir(parents=True, exist_ok=True)
        loader.write_bytes((ROOT / vfp.STARTUP_LOADER_COMPANION["source"]).read_bytes())
        seeded[loader.relative_to(folder).as_posix()] = loader.read_bytes()
        (folder / "my notes.txt").write_text("the player's own file", encoding="utf-8")
        (folder / "Images").mkdir(exist_ok=True)
        (folder / "Images" / "my_art.png").write_bytes(b"the player's own art")
        return seeded

    def publish(self, game: str, selection: list[str]):
        import shutil
        import tempfile
        import json
        build = build_of(game)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        folder = Path(temp.name) / build.title
        folder.mkdir()
        shutil.copy2(stock_path(game), folder / build.input_name)
        seeded = self.seed(folder, game)
        before = {p.relative_to(folder).as_posix(): p.read_bytes() for p in folder.rglob("*") if p.is_file()}
        output, log_path = vfp.apply_patch(folder / build.input_name, "collection_progression",
                                           fun_patch_ids=selection)
        log = json.loads(log_path.read_text(encoding="utf-8"))
        after = {p.relative_to(output.parent).as_posix(): p for p in output.parent.rglob("*") if p.is_file()}
        return seeded, before, after, log, folder

    def test_only_the_selected_companions_remain(self):
        for game, selection in (("vv1", ["vv1_write_village_statistics"]),
                                ("vv3", ["vv3_enable_origins_exclusive_features", "vv3_cause_of_death",
                                         "vv3_write_parentage_log"])):
            with self.subTest(game=game):
                seeded, before, after, log, source_folder = self.publish(game, selection)
                features = vfp._attach_automatic_companions(
                    game, vfp._selected_fun_patches(build_of(game), selection))
                shipped = {vfp._safe_companion_destination(i["destination"]).as_posix()
                           for f in features for i in f.raw.get("companion_files", [])}
                for relative in seeded:
                    with self.subTest(file=relative):
                        self.assertEqual(relative in after, relative in shipped)
                removed = {r["path"] for r in log["removed_unselected_companions"]}
                self.assertEqual(removed, {r for r in seeded if r not in shipped})
                # Nothing else changed: the player's file, the art that is not
                # the patcher's, and the source folder itself.
                self.assertEqual(after["my notes.txt"].read_text(encoding="utf-8"), "the player's own file")
                self.assertEqual(after["Images/my_art.png"].read_bytes(), b"the player's own art")
                self.assertEqual({p.relative_to(source_folder).as_posix(): p.read_bytes()
                                  for p in source_folder.rglob("*") if p.is_file()}, before)

    def test_the_mutation_without_the_cleanup_keeps_the_stale_companions(self):
        original = vfp._remove_unselected_companions
        vfp._remove_unselected_companions = lambda *a, **k: []
        self.addCleanup(setattr, vfp, "_remove_unselected_companions", original)
        seeded, _, after, _, _ = self.publish("vv1", ["vv1_write_village_statistics"])
        fix_huts = f"{FILES}/VVFP Fix Huts.dll"
        self.assertIn(fix_huts, seeded)
        self.assertIn(fix_huts, after)


TOOLCHAIN = Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231")
SDK = Path(r"C:\Program Files (x86)\Windows Kits\10")


class AFaultingCompanionNeverStopsTheGame(unittest.TestCase):
    """A companion whose VvfpStartup faults is abandoned and every other
    companion still starts: run for real (32-bit, on this machine) with the
    shipped VVFP Startup.dll, a companion that writes to address 0 and one
    that records it was started."""

    FAULTING = r'''
#include <windows.h>
#pragma comment(linker, "/EXPORT:VvfpStartup=_VvfpStartup@8")
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    (void)game; (void)shipped;
    *(volatile int *)0 = 1;
}
'''
    RECORDING = r'''
#include <windows.h>
#pragma comment(linker, "/EXPORT:VvfpStartup=_VvfpStartup@8")
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    wchar_t path[1024];
    DWORD n = GetModuleFileNameW(NULL, path, 1024);
    HANDLE f;
    while (n > 0 && path[n - 1] != L'\\') { --n; }
    lstrcpyW(path + n, L"started.txt");
    f = CreateFileW(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, 0, NULL);
    if (f != INVALID_HANDLE_VALUE) {
        char text[32];
        DWORD w;
        wsprintfA(text, "%d %u", game, shipped);
        WriteFile(f, text, lstrlenA(text), &w, NULL);
        CloseHandle(f);
    }
}
'''
    HOST = r'''
#include <windows.h>
#include <stdio.h>
typedef void (__stdcall *startup_fn)(int, unsigned int);
int main(void) {
    wchar_t path[1024];
    DWORD n = GetModuleFileNameW(NULL, path, 1024);
    HMODULE m;
    startup_fn startup;
    while (n > 0 && path[n - 1] != L'\\') { --n; }
    lstrcpyW(path + n, L"Virtual Villagers Fun Patcher Files\\VVFP Startup.dll");
    m = LoadLibraryW(path);
    startup = m ? (startup_fn)GetProcAddress(m, "VvfpStartup") : NULL;
    if (!startup) { puts("no loader"); return 2; }
    startup(3, 0x1u | 0x10u);     /* the Origins companion and Save Reset (bit 4) */
    puts("survived");
    return 0;
}
'''

    # The control: the same companion called directly, with no handler,
    # takes the process down -- so the fault is real.
    DIRECT = r'''
#include <windows.h>
typedef void (__stdcall *startup_fn)(int, unsigned int);
int main(void) {
    wchar_t path[1024];
    DWORD n = GetModuleFileNameW(NULL, path, 1024);
    HMODULE m;
    while (n > 0 && path[n - 1] != L'\\') { --n; }
    lstrcpyW(path + n, L"Virtual Villagers Fun Patcher Files\\VVFP Origins Icons.dll");
    m = LoadLibraryW(path);
    ((startup_fn)GetProcAddress(m, "VvfpStartup"))(3, 1);
    return 0;
}
'''

    def compile(self, folder: Path, source: str, out: str, dll: bool) -> None:
        import subprocess
        c = folder / (out + ".c")
        c.write_text(source, encoding="utf-8")
        version = "10.0.26100.0"
        args = [str(TOOLCHAIN / "bin" / "Hostx64" / "x86" / "cl.exe"), "/nologo", "/O2", "/MT",
                "/I", str(TOOLCHAIN / "include"), "/I", str(SDK / "Include" / version / "um"),
                "/I", str(SDK / "Include" / version / "shared"), "/I", str(SDK / "Include" / version / "ucrt")]
        if dll:
            args.append("/LD")
        args += [str(c), "/link", f"/OUT:{folder / out}",
                 f"/LIBPATH:{TOOLCHAIN / 'lib' / 'x86'}", f"/LIBPATH:{SDK / 'Lib' / version / 'um' / 'x86'}",
                 f"/LIBPATH:{SDK / 'Lib' / version / 'ucrt' / 'x86'}", "kernel32.lib", "user32.lib"]
        result = subprocess.run(args, cwd=folder, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless((TOOLCHAIN / "bin" / "Hostx64" / "x86" / "cl.exe").exists(), "MSVC is not installed")
    def test_a_fault_in_one_companion_skips_only_that_one(self):
        import shutil
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            files = folder / FILES
            files.mkdir()
            self.compile(files, self.FAULTING, "VVFP Origins Icons.dll", True)
            self.compile(files, self.RECORDING, "VVFP Save Reset.dll", True)
            self.compile(folder, self.HOST, "host.exe", False)
            self.compile(folder, self.DIRECT, "direct.exe", False)
            control = subprocess.run([str(folder / "direct.exe")], capture_output=True, text=True, timeout=60)
            self.assertNotEqual(control.returncode, 0)
            shutil.copy2(ROOT / vfp.STARTUP_LOADER_COMPANION["source"], files / vfp.STARTUP_LOADER_DLL)
            result = subprocess.run([str(folder / "host.exe")], capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("survived", result.stdout)
            self.assertEqual((folder / "started.txt").read_text(encoding="ascii"), "3 17")


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
class DeepInstallFolders(unittest.TestCase):
    """Codex (#537): the stub checks the FOLDER plus what it appends, not the
    executable's whole path.  It appends "Virtual Villagers Fun Patcher
    Files\\VVFP Startup.dll" to the executable's folder in a buffer of
    STARTUP_LOADER_PATH_WCHARS (twice MAX_PATH): a folder that leaves room for
    it (with its NUL) starts every companion, one character more starts none
    -- and in both cases the game itself starts, with WinMain entered exactly
    as the C runtime called it."""

    def test_the_deepest_folder_that_fits_and_one_past_it(self):
        game = "vv3"
        selection = tuple(i for i in public_ids(game) if i not in POPULATION_256)
        exe, shipped, _ = published(game, "collection_progression", selection)
        name = build_of(game).input_name
        tail = len(vfp.STARTUP_LOADER_TAIL) // 2          # WCHARs, with the NUL
        deepest = vfp.STARTUP_LOADER_PATH_WCHARS - tail
        self.assertLess(deepest + len(name), vfp.STARTUP_LOADER_PATH_WCHARS)   # the exe's path fits
        for length, starts in ((deepest, True), (deepest + 1, False)):
            folder = "C:\\" + "d" * (length - 4) + "\\"
            self.assertEqual(len(folder), length)
            with self.subTest(folder_length=length):
                machine = StartupMachine(exe, name, shipped, game_dir=folder)
                call_va, winmain = vfp.STARTUP_LOADER_WINMAIN_CALL[game]
                result = machine.run_to_winmain(call_va, winmain)
                self.assertEqual(result["registers_at_winmain"], result["registers_before"])
                self.assertEqual(result["esp_at_winmain"], result["esp_before_call"] - 4)
                self.assertEqual({m.name for m in machine.modules.values()} == set(shipped), starts)
                if not starts:
                    self.assertEqual(machine.modules, {})

    def test_an_executable_path_the_buffer_cannot_hold_starts_the_game(self):
        game = "vv5"
        selection = tuple(i for i in public_ids(game) if i not in POPULATION_256)
        exe, shipped, _ = published(game, "collection_progression", selection)
        name = build_of(game).input_name
        folder = "C:\\" + "d" * (vfp.STARTUP_LOADER_PATH_WCHARS - len(name) - 4) + "\\"
        self.assertEqual(len(folder + name), vfp.STARTUP_LOADER_PATH_WCHARS)   # cut short
        machine = StartupMachine(exe, name, shipped, game_dir=folder)
        call_va, winmain = vfp.STARTUP_LOADER_WINMAIN_CALL[game]
        result = machine.run_to_winmain(call_va, winmain)
        self.assertEqual(result["registers_at_winmain"], result["registers_before"])
        self.assertEqual(machine.modules, {})


# A game folder whose name the ANSI code page cannot spell: accented Latin
# and Japanese, as an owner might install to.
UNICODE_FOLDER = "C:\\Jeux vidéo\\村人たち\\Virtual Villagers\\"
FILES = vfp.patcher_files.PATCHER_FILES_FOLDER


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
class AUnicodeGameFolder(unittest.TestCase):
    """Every add-on of every build starts in a game folder with characters
    outside the ANSI code page: the stub and every companion find their
    files with the wide API, by full path in the patcher's folder."""

    def test_every_build_starts_every_companion(self):
        for game in GAMES:
            for name, selection in selections(game).items():
                if not name.startswith("every"):
                    continue
                with self.subTest(game=game, selection=name):
                    exe, shipped, features = published(game, "collection_progression", tuple(selection))
                    machine = StartupMachine(exe, build_of(game).input_name, shipped,
                                             game_dir=UNICODE_FOLDER)
                    call_va, winmain = vfp.STARTUP_LOADER_WINMAIN_CALL[game]
                    before = {va: machine.code(va, len(stock)) for va, stock, _ in declared_detours(features)}
                    result = machine.run_to_winmain(call_va, winmain)
                    self.assertEqual(result["registers_at_winmain"], result["registers_before"])
                    self.assertEqual({m.name for m in machine.modules.values()}, set(shipped))
                    for module in machine.modules.values():
                        self.assertEqual(module.path, UNICODE_FOLDER + FILES + "\\" + module.name)
                    for va, stock, what in declared_detours(features):
                        if before[va] == stock:
                            self.assertNotEqual(machine.code(va, len(stock)), stock, what)

    def test_the_ansi_path_would_load_nothing_there(self):
        """The control: the same folder as the ANSI API renders it ('?' for
        what the code page cannot spell) is not the folder the files are in,
        so a loader built on it would start nothing."""
        self.assertIn("?", UNICODE_FOLDER.encode("cp1252", errors="replace").decode("cp1252"))
        game = "vv1"
        selection = tuple(i for i in public_ids(game) if i not in POPULATION_256)
        exe, shipped, _ = published(game, "collection_progression", selection)
        machine = StartupMachine(exe, build_of(game).input_name, shipped, game_dir=UNICODE_FOLDER)
        ansi = UNICODE_FOLDER.encode("cp1252", errors="replace").decode("cp1252")
        machine.files_dir = ansi + FILES + "\\"          # where an ANSI loader would look
        machine.run_to_winmain(*vfp.STARTUP_LOADER_WINMAIN_CALL[game])
        self.assertEqual(machine.modules, {})


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
class TheExecutableNeverSearchesForACompanion(unittest.TestCase):
    """Code the patcher writes into the executables names companions with
    `push "VVFP ... .dll"; call [LoadLibraryA]` -- the DLL search order. Every
    published build routes each of those calls to GetModuleHandleA, which
    only finds a module VVFP Startup.dll already loaded from the patcher's
    folder; and every companion such a call names is one the loader starts
    in that build."""

    def sites(self, exe: bytes, api: bytes) -> list[str]:
        pe = pefile.PE(data=exe)
        slot = next(i.address for e in pe.DIRECTORY_ENTRY_IMPORT for i in e.imports if i.name == api)
        call = b"\xFF\x15" + struct.pack("<I", slot)
        names = []
        for m in re.finditer(re.escape(call), exe):
            at = m.start()
            if exe[at - 5] != 0x68:
                continue
            va = struct.unpack_from("<I", exe, at - 4)[0]
            try:
                off = pe.get_offset_from_rva(va - 0x400000)
            except Exception:
                continue
            text = exe[off:exe.find(b"\0", off)]
            if text.startswith(b"VVFP "):
                names.append(text.decode("ascii"))
        return names

    def test_every_build(self):
        for game in GAMES:
            for mode in MODES:
                for name, selection in selections(game).items():
                    with self.subTest(game=game, mode=mode, selection=name):
                        exe, shipped, features = published(game, mode, tuple(selection))
                        self.assertEqual(self.sites(exe, b"LoadLibraryA"), [])
                        attached = vfp._attach_automatic_companions(
                            game, vfp._selected_fun_patches(build_of(game), list(selection)))
                        mask = vfp._startup_loader_mask(game, attached)
                        started = {vfp.STARTUP_LOADER_ORIGINS[game]} if mask & 1 else set()
                        started |= {n for i, n in enumerate(vfp.STARTUP_LOADER_COMPANIONS) if mask & (1 << (i + 1))}
                        # A companion the build ships is started before the
                        # game runs; one it does not ship (an optional partner,
                        # e.g. Work First beside Fix Huts) is simply not found,
                        # exactly as when the old LoadLibraryA found no file.
                        for named in self.sites(exe, b"GetModuleHandleA"):
                            if named in shipped:
                                self.assertIn(named, started)

    def test_the_render_alone_still_searches(self):
        """The control: before publication the stubs are LoadLibraryA calls,
        so the check above would fail without the routing."""
        game = "vv5"
        selection = [i for i in public_ids(game) if i not in POPULATION_256]
        data, _ = vfp.render_patched_bytes(stock_path(game), build_of(game), "collection_progression", selection)
        self.assertTrue(self.sites(bytes(data), b"LoadLibraryA"))



class AFaultingBridgeNeverStopsTheOthers(AFaultingCompanionNeverStopsTheGame):
    """Codex (#537): one Origins companion runs many installs in its
    VvfpStartup.  A fault in one of them (here Builders Fix Huts When Idle,
    in the middle of A New Home's list) must not leave the installs after it
    -- Story / Cheat Upgrades and Cause of Death -- unarmed.  Run for real
    (32-bit) with the SHIPPED VVFP Startup.dll and the SHIPPED A New Home
    Origins companion; the three companions are stand-ins: Fix Huts faults in
    its install, Story and Cause of Death record that they were installed."""

    test_a_fault_in_one_companion_skips_only_that_one = None   # the parent's own case runs there

    FIX_HUTS = r"""
#include <windows.h>
#pragma comment(linker, "/EXPORT:VvfpFixHutsInstall=_VvfpFixHutsInstall@4")
int __stdcall VvfpFixHutsInstall(int game) {
    (void)game;
    return *(volatile int *)0;
}
"""
    RECORDER = r"""
#include <windows.h>
static void note(const wchar_t *what) {
    wchar_t path[1024];
    DWORD n = GetModuleFileNameW(NULL, path, 1024);
    HANDLE f;
    DWORD w;
    while (n > 0 && path[n - 1] != L'\\') { --n; }
    lstrcpyW(path + n, what);
    f = CreateFileW(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, 0, NULL);
    if (f != INVALID_HANDLE_VALUE) { WriteFile(f, "1", 1, &w, NULL); CloseHandle(f); }
}
"""
    STORY = RECORDER + r"""
#pragma comment(linker, "/EXPORT:VvfpStoryInstall=_VvfpStoryInstall@4")
#pragma comment(linker, "/EXPORT:VvfpStoryArm=_VvfpStoryArm@4")
#pragma comment(linker, "/EXPORT:VvfpStoryActive=_VvfpStoryActive@4")
#pragma comment(linker, "/EXPORT:VvfpStoryPickIslandEvent=_VvfpStoryPickIslandEvent@8")
#pragma comment(linker, "/EXPORT:VvfpStoryCustomIslandEvent=_VvfpStoryCustomIslandEvent@8")
#pragma comment(linker, "/EXPORT:VvfpStoryAttachHost=_VvfpStoryAttachHost@8")
int __stdcall VvfpStoryInstall(int g) { (void)g; return 1; }
int __stdcall VvfpStoryArm(int g) { (void)g; note(L"story armed.txt"); return 1; }
int __stdcall VvfpStoryActive(int g) { (void)g; return 1; }
int __stdcall VvfpStoryPickIslandEvent(int g, HWND w) { (void)g; (void)w; return 0; }
int __stdcall VvfpStoryCustomIslandEvent(int g, HWND w) { (void)g; (void)w; return 0; }
int __stdcall VvfpStoryAttachHost(int g, const void *h) { (void)g; (void)h; return 1; }
"""
    CAUSE = RECORDER + r"""
#pragma comment(linker, "/EXPORT:VvfpCauseInstall=_VvfpCauseInstall@8")
#pragma comment(linker, "/EXPORT:VvfpCauseTick=_VvfpCauseTick@4")
int __stdcall VvfpCauseInstall(int g, const void *h) { (void)g; (void)h; note(L"cause installed.txt"); return 1; }
void __stdcall VvfpCauseTick(int g) { (void)g; }
"""
    HOST1 = r"""
#include <windows.h>
#include <stdio.h>
typedef void (__stdcall *startup_fn)(int, unsigned int);
int main(int argc, char **argv) {
    wchar_t path[1024];
    DWORD n = GetModuleFileNameW(NULL, path, 1024);
    HMODULE m;
    startup_fn startup;
    unsigned int shipped = (unsigned int)strtoul(argv[1], NULL, 0);
    (void)argc;
    while (n > 0 && path[n - 1] != L'\\') { --n; }
    lstrcpyW(path + n, L"Virtual Villagers Fun Patcher Files\\VVFP Startup.dll");
    m = LoadLibraryW(path);
    startup = m ? (startup_fn)GetProcAddress(m, "VvfpStartup") : NULL;
    if (!startup) { puts("no loader"); return 2; }
    startup(1, shipped);
    puts("survived");
    return 0;
}
"""

    @unittest.skipUnless((TOOLCHAIN / "bin" / "Hostx64" / "x86" / "cl.exe").exists(), "MSVC is not installed")
    def test_a_fault_in_one_bridge_skips_only_that_one(self):
        import shutil
        import subprocess
        import tempfile
        index = {name: i for i, name in enumerate(vfp.STARTUP_LOADER_COMPANIONS)}
        bit = lambda name: 1 << (index[name] + 1)   # noqa: E731
        shipped = 1 | bit("VVFP Fix Huts.dll") | bit("VVFP Story Upgrades.dll") | bit("VVFP Cause of Death.dll")
        with tempfile.TemporaryDirectory() as temp:
            build = Path(temp) / "build"
            build.mkdir()
            self.compile(build, self.FIX_HUTS, "VVFP Fix Huts.dll", True)
            self.compile(build, self.STORY, "VVFP Story Upgrades.dll", True)
            self.compile(build, self.CAUSE, "VVFP Cause of Death.dll", True)
            self.compile(build, self.HOST1, "host.exe", False)
            # The game folder's name is outside the ANSI code page: the
            # shipped loader and the shipped Origins companion's bridges
            # still find every companion (wide API, full path).
            folder = Path(temp) / "Jeux vidéo 村人たち"
            files = folder / FILES
            files.mkdir(parents=True)
            shutil.copy2(build / "host.exe", folder / "host.exe")
            for name in ("VVFP Fix Huts.dll", "VVFP Story Upgrades.dll", "VVFP Cause of Death.dll"):
                shutil.copy2(build / name, files / name)
            shutil.copy2(ROOT / vfp.STARTUP_LOADER_COMPANION["source"], files / vfp.STARTUP_LOADER_DLL)
            shutil.copy2(ROOT / "assets" / "origins" / "VVFP VV1 Origins Icons.dll",
                         files / "VVFP VV1 Origins Icons.dll")
            result = subprocess.run([str(folder / "host.exe"), hex(shipped)], capture_output=True,
                                    text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("survived", result.stdout)
            # The installs after the faulting one still ran.
            self.assertTrue((folder / "story armed.txt").is_file())
            self.assertTrue((folder / "cause installed.txt").is_file())
            # Control: Fix Huts really is reached and really faults -- with
            # its bit off nothing faults, and the others are armed the same.
            for f in ("story armed.txt", "cause installed.txt"):
                (folder / f).unlink()
            result = subprocess.run([str(folder / "host.exe"), hex(shipped & ~bit("VVFP Fix Huts.dll"))],
                                    capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0)
            self.assertTrue((folder / "cause installed.txt").is_file())


if __name__ == "__main__":
    unittest.main()
