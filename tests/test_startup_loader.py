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
                block = vfp._startup_loader_block(va, int(game[2]), mask, slots[b"GetModuleFileNameA"],
                                                  slots[b"LoadLibraryA"], slots[b"GetProcAddress"], winmain)
                self.assertEqual(pe.get_data(section.VirtualAddress, len(block)), block)
                self.assertEqual(pe.get_data(call_va - 0x400000, 5),
                                 b"\xE8" + struct.pack("<i", va + vfp.STARTUP_LOADER_CODE_OFFSET - (call_va + 5)))

    def test_every_companion_dll_is_one_the_loader_knows(self):
        source = (ROOT / "native" / "vvfp_startup" / "vvfp_startup.c").read_text(encoding="utf-8")
        named = set(re.findall(r'"(VVFP [^"]+\.dll)"', source))
        shipped = {str(item["destination"]) for p in vfp.load_fun_patches()
                   for item in p.raw.get("companion_files", [])
                   if str(item.get("destination", "")).lower().endswith(".dll")}
        self.assertEqual(shipped - named, set())

    def test_the_loader_and_the_patcher_number_the_companions_alike(self):
        source = (ROOT / "native" / "vvfp_startup" / "vvfp_startup.c").read_text(encoding="utf-8")
        body = source[source.index("COMPANIONS[] = {"):]
        body = body[:body.index("};")]
        golden = re.search(r'GOLDEN_MUSHROOM\[\] = "([^"]+)"', source).group(1)
        self.assertEqual(tuple(re.findall(r'"([^"]+)"', body)) + (golden,), vfp.STARTUP_LOADER_COMPANIONS)
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
        self.assertTrue(all(full for _, _, full in loads), f"a load by bare name: {loads}")
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


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
class OnlyThisBuildsCompanions(unittest.TestCase):
    """Codex (#537): a patcher DLL in the folder that this build does not ship
    -- copied along with the game folder, or left by another build -- is
    never loaded, so it can never install a patch nobody selected."""

    def test_unshipped_dlls_in_the_folder_are_never_loaded(self):
        stale = {
            "vv1": ("VVFP VV1 Origins Icons.dll", "assets/origins/VVFP VV1 Origins Icons.dll"),
            "vv3": ("VVFP Origins Icons.dll", "data/candidates/VVFP VV3 Safe Upgrades.dll"),
        }
        extra_names = {"VVFP Fix Huts.dll": ROOT / "assets" / "fix_huts" / "VVFP Fix Huts.dll",
                       "VVFP Cause of Death.dll": ROOT / "assets" / "cause_of_death" / "VVFP Cause of Death.dll"}
        for game, (origins, source) in stale.items():
            with self.subTest(game=game):
                selection = (f"{game}_write_village_statistics",)
                exe, shipped, _ = published(game, "collection_progression", selection)
                folder = dict(shipped, **extra_names, **{origins: ROOT / source})
                machine = StartupMachine(exe, build_of(game).input_name, folder)
                call_va, winmain = vfp.STARTUP_LOADER_WINMAIN_CALL[game]
                machine.run_to_winmain(call_va, winmain)
                self.assertEqual({m.name for m in machine.modules.values()}, set(shipped))


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
class DeepInstallFolders(unittest.TestCase):
    """Codex (#537): the stub checks the FOLDER plus the loader's name against
    MAX_PATH, not the executable's whole path, so a deep folder whose
    executable name alone would not fit still starts every companion."""

    def test_a_deep_folder_still_starts_every_companion(self):
        game = "vv3"
        selection = tuple(i for i in public_ids(game) if i not in POPULATION_256)
        exe, shipped, _ = published(game, "collection_progression", selection)
        name = build_of(game).input_name
        limit = vfp.STARTUP_LOADER_PATH_BYTES            # MAX_PATH, with the NUL
        deepest = limit - 1 - len(name)                  # the executable's path is 259 characters
        # The old check (the whole path against MAX_PATH less the loader's
        # name) refused every path of 243 characters or more.
        self.assertGreaterEqual(deepest + len(name), limit - len(vfp.STARTUP_LOADER_DLL) - 1)
        for length, starts in ((deepest, True), (deepest + 1, False)):   # + 1: truncated
            folder = "C:\\" + "d" * (length - 4) + "\\"
            self.assertEqual(len(folder), length)
            with self.subTest(folder_length=length):
                machine = StartupMachine(exe, name, shipped, game_dir=folder)
                call_va, winmain = vfp.STARTUP_LOADER_WINMAIN_CALL[game]
                result = machine.run_to_winmain(call_va, winmain)
                self.assertEqual(result["registers_at_winmain"], result["registers_before"])
                self.assertEqual({m.name for m in machine.modules.values()} == set(shipped), starts)


if __name__ == "__main__":
    unittest.main()
