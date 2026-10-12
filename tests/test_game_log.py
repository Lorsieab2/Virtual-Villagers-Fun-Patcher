"""Keep the Game's Own Log (ldwLog.txt): all five games (native/vvfp_game_log).

Every Virtual Villagers game carries the LDW engine's log writer for
Documents\\LDW\\<exe name>\\ldwLog.txt.  Static analysis of the five stock
executables (IDA 9.4, 2026-10-11) found it switched off nowhere: no enable flag,
no stub, no jumped-over call -- every call site below is live -- but the base
game opens the file "wt" (each run erases the last), buffers it until a clean
exit, and writes only when something goes wrong.  The companion replaces the
writer's first instruction with its own writer (append, write-through, repeat
and burst limits, roll-over at 4 MiB).

These tests pin, against the stock executables (skipped as a missing input
when they are absent):
* each game's writer and its 16 verified bytes, in the C source, the manifest
  and every rendered build in every mode (so the companion installs in all of
  them, the 256 builds included);
* every direct call to the writer, with the format string each one passes --
  so "every line the game can write" in the descriptions is the whole list;
* nothing jumps into the six bytes the companion replaces;
and, without the executables: the rows, the startup loader bit, default-on and
Select All, the shipped DLL's exports, and the C harness that runs the
companion's own writer (line format, append across runs, repeats, the cap,
roll-over, unreadable values, the install guard).
"""
from __future__ import annotations

import functools
import hashlib
import importlib.util
import json
import re
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as patcher  # noqa: E402

try:
    import pefile
    HAVE_PEFILE = True
except ImportError:  # pragma: no cover
    HAVE_PEFILE = False

GAMES = ("vv1", "vv2", "vv3", "vv4", "vv5")
MODES = ("stock", "collection_progression", "immediate_fixed")
STOCK_DIR = ROOT / "research" / "stock-executables"
EXE = {
    "vv1": "Virtual Villagers - A New Home.exe",
    "vv2": "Virtual Villagers - The Lost Children.exe",
    "vv3": "Virtual Villagers - The Secret City.exe",
    "vv4": "Virtual Villagers - The Tree of Life.exe",
    "vv5": "Virtual Villagers - New Believers.exe",
}
STOCK = {game: STOCK_DIR / name for game, name in EXE.items()}
HAVE_STOCK = HAVE_PEFILE and all(path.is_file() for path in STOCK.values())
NO_STOCK = "stock executables are not available"
NATIVE = ROOT / "native" / "vvfp_game_log"
SOURCE = NATIVE / "vvfp_game_log.c"
DLL = ROOT / "assets" / "game_log" / "VVFP Game Log.dll"
TEST_DLL = ROOT / "tests" / "test_dlls" / "VVFP Game Log.test.dll"
IMAGE_BASE = 0x400000

WRITER = {"vv1": 0x40A970, "vv2": 0x40AB70, "vv3": 0x40B800, "vv4": 0x40B6C0, "vv5": 0x40BBB0}
WRITER_STOCK = {
    "vv1": "56578B7C240C8B37833E00753A8B4608",
    "vv2": "56578B7C240C8B37833E00753A8B4608",
    "vv3": "56578B7C240C8B37833E00753A8B4608",
    "vv4": "56578B7C240C8B37833E0075388B4608",
    "vv5": "56578B7C240C8B37833E0075388B4608",
}
FONT = "Font Image not found: %s\n"
GRAPHIC = " Missing Graphic -> %s"
SOUND = "ldwSoundFx Missing File ->%s"
TIMER = "Seconds Timer out of bounds!"
TIP = "Displaying Tip (%d) message!"
SM_NEAR = "String Table (sm.xml) malformed near %s"
SM_END = "String Table (sm.xml) malformed looking for </Text> after %s"
HEAL = "%s could not find someone to heal."
STUCK = "%s is stuck!"
NO_WAY = "%s cannot get from %d, %d (isBlocking=%s) to %d, %d (isBlocking=%s)"
SHACK = "%s is going to the love shack door at %d, %d (isBlocking=%s)"
# Every direct call to the writer in each stock executable, and its format.
CALLS = {
    "vv1": {0x4022E7: FONT, 0x40A715: GRAPHIC, 0x40AF57: SOUND},
    "vv2": {0x402577: FONT, 0x40A915: GRAPHIC, 0x40B937: SOUND, 0x42F1F1: TIMER, 0x42F37B: TIP},
    "vv3": {0x4025B7: FONT, 0x40B5B5: GRAPHIC, 0x40C5C7: SOUND, 0x42F635: SM_NEAR, 0x42F68E: SM_END,
            0x45B940: HEAL, 0x4688F9: TIMER},
    "vv4": {0x402875: FONT, 0x40B248: GRAPHIC, 0x40C4F8: SOUND, 0x43FC28: TIMER, 0x44D8B7: SM_NEAR,
            0x44D90E: SM_END, 0x465149: HEAL},
    "vv5": {0x402805: FONT, 0x40B748: GRAPHIC, 0x40C9E8: SOUND, 0x442879: TIMER, 0x450BC7: SM_NEAR,
            0x450C1E: SM_END, 0x46930B: STUCK, 0x469502: NO_WAY, 0x46E1C9: HEAL, 0x474536: SHACK},
}
FORMATS = {fmt for calls in CALLS.values() for fmt in calls.values()}
# The lines only one game's code contains: never claimed for another game.
ONLY_IN = {TIP: {"vv2"}, STUCK: {"vv5"}, NO_WAY: {"vv5"}, SHACK: {"vv5"}}

VS_TOOLS = Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231")
CL = VS_TOOLS / "bin" / "Hostx64" / "x86" / "cl.exe"
SDK = Path(r"C:\Program Files (x86)\Windows Kits\10")
SDK_VERSION = "10.0.26100.0"


def _manifest(game: str) -> dict:
    return json.loads((ROOT / "data" / f"{game}_game_log_feature.json").read_text(encoding="utf-8"))


@functools.lru_cache(maxsize=None)
def _image(game: str) -> bytes:
    return pefile.PE(str(STOCK[game])).get_memory_mapped_image()


@functools.lru_cache(maxsize=None)
def _builds():
    return {build.id: build for build in patcher.load_builds()}


def _mapped(data: bytes) -> bytes:
    return pefile.PE(data=data).get_memory_mapped_image()


def _cstring(image: bytes, va: int) -> str:
    at = va - IMAGE_BASE
    return image[at:image.index(b"\0", at)].decode("latin-1")


def _direct_calls(image: bytes, target: int) -> list[int]:
    found = []
    text_start = 0x1000
    text_end = len(image)
    at = image.find(b"\xE8", text_start)
    while 0 <= at < text_end - 5:
        rel = struct.unpack_from("<i", image, at + 1)[0]
        if IMAGE_BASE + at + 5 + rel == target:
            found.append(IMAGE_BASE + at)
        at = image.find(b"\xE8", at + 1)
    return found


def _pushed_format(image: bytes, call: int) -> str | None:
    """The string a `push imm32` in the 48 bytes before `call` points at, nearest first."""
    best = None
    for at in range(call - IMAGE_BASE - 48, call - IMAGE_BASE):
        if image[at] == 0x68:
            va = struct.unpack_from("<I", image, at + 1)[0]
            if IMAGE_BASE + 0x1000 <= va < IMAGE_BASE + len(image):
                try:
                    text = _cstring(image, va)
                except ValueError:
                    continue
                if text in FORMATS:
                    best = text
    return best


class SourceAndRows(unittest.TestCase):
    def test_the_source_verifies_each_games_writer(self):
        source = SOURCE.read_text(encoding="utf-8")
        for number, game in enumerate(GAMES, start=1):
            stock = ", ".join(f"0x{b:02X}" for b in bytes.fromhex(WRITER_STOCK[game]))
            self.assertIn(f"{{0x{WRITER[game]:X}, {{{stock}}}}}", source, game)
        self.assertIn("#define ROLL_BYTES (4u * 1024u * 1024u)", source)
        self.assertIn("#define RATE_LINES 1000u", source)
        self.assertIn("#define REPEAT_SECONDS 60", source)
        self.assertIn('L"\\\\ldwLog.txt"', source)
        self.assertIn('L"\\\\ldwLog "', source)
        self.assertIn("FILE_APPEND_DATA", source)
        self.assertNotIn("DeleteFile", source.split("#ifdef VVFP_TEST")[0])

    def test_the_rows(self):
        sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
        public = {p.id for p in patcher.load_public_fun_patches()}
        for game in GAMES:
            with self.subTest(game=game):
                row = _manifest(game)
                self.assertEqual(row["id"], f"{game}_game_log")
                self.assertIn(row["id"], public)
                self.assertEqual(row["game_id"], game)
                self.assertEqual(row["name"], "Keep the Game's Own Log (ldwLog.txt)")
                self.assertEqual(row["patches"], [])
                self.assertNotIn("needs_on", row)
                self.assertNotIn("dependencies", row)
                self.assertEqual(row["companion_files"],
                                 [{"source": "assets/game_log/VVFP Game Log.dll",
                                   "destination": "VVFP Game Log.dll", "sha256": sha}])
                detour = row["runtime_detours"]
                self.assertEqual(len(detour), 1)
                self.assertEqual(detour[0]["va"], f"{WRITER[game]:#x}")
                self.assertEqual(detour[0]["stock_bytes"], WRITER_STOCK[game])
                description = row["description"]
                self.assertTrue(description.endswith("**Needs no other patch.**"))
                for words in ("ldwLog.txt", "Documents\\LDW\\<game executable name>\\", "ldwLog 1.txt",
                              "4 MB", "---- Game started ----", "nothing is ever deleted"):
                    self.assertIn(words, description)
                # every call site is listed, and no line from another game's code is claimed
                listed = "\n".join(row["behavior_changes"])
                for va, fmt in CALLS[game].items():
                    self.assertIn(f"Call at {va:#x} writes \"{fmt.rstrip(chr(10))}\"", listed)
                for fmt, owners in ONLY_IN.items():
                    if game not in owners:
                        self.assertNotIn(fmt, listed)

    def test_the_generator_reproduces_the_rows(self):
        if not HAVE_STOCK:
            self.skipTest(NO_STOCK)
        spec = importlib.util.spec_from_file_location("build_game_log_features",
                                                      ROOT / "scripts" / "build_game_log_features.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
        for game in GAMES:
            self.assertEqual(module.row(game, sha), _manifest(game), game)
            self.assertEqual({va: fmt for va, fmt, _ in module.CALLS[game]}, CALLS[game])

    def test_started_by_the_startup_loader(self):
        self.assertIn("VVFP Game Log.dll", patcher.STARTUP_LOADER_COMPANIONS)
        self.assertEqual(patcher.STARTUP_LOADER_COMPANIONS[-1], "VVFP Game Log.dll")
        header = (ROOT / "native" / "shared" / "startup_companions.h").read_text(encoding="utf-8")
        self.assertIn('    "VVFP Storytelling.dll",\n    "VVFP Game Log.dll",\n    /* APPEND ONLY', header)
        self.assertIn("void __stdcall VvfpStartup(int game, unsigned int shipped)",
                      SOURCE.read_text(encoding="utf-8"))
        self.assertIn(b"VVFP Game Log.dll", (ROOT / "assets" / "startup" / "VVFP Startup.dll").read_bytes())
        records = {p.id: p for p in patcher.load_fun_patches()}
        bit = 1 << (patcher.STARTUP_LOADER_COMPANIONS.index("VVFP Game Log.dll") + 1)
        self.assertLess(bit, patcher.STARTUP_LOADER_STORY_CHARGES)
        for game in GAMES:
            self.assertEqual(patcher._startup_loader_mask(game, [records[f"{game}_game_log"]]) & bit, bit)
            self.assertEqual(patcher._startup_loader_mask(game, []) & bit, 0)

    def test_on_by_default_in_select_all_and_owners_defaults(self):
        from vv_fun_patcher_gui import (default_fun_patch_selection, owners_default_fun_patch_selection,
                                        select_all_fun_patch_selection)
        for game in GAMES:
            self.assertTrue(default_fun_patch_selection(f"{game}_game_log"))
            self.assertTrue(owners_default_fun_patch_selection(f"{game}_game_log"))
            self.assertTrue(select_all_fun_patch_selection(f"{game}_game_log"))
        self.assertNotIn("_game_log", " ".join(patcher.EXPERIMENTAL_FUN_PATCH_IDS))

    def test_registered_bundled_documented(self):
        source = (ROOT / "src" / "vv_fun_patcher.py").read_text(encoding="utf-8")
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        guide = json.loads((ROOT / "data" / "how_to_use.json").read_text(encoding="utf-8"))
        self.assertIn("assets/game_log/VVFP Game Log.dll", release)
        self.assertIn('f"vv{game_number}_game_log_feature.json"', source)
        guided = {i for entry in guide["patches"] for i in entry.get("ids", [])}
        for game in GAMES:
            self.assertIn(f"data/{game}_game_log_feature.json", release)
            self.assertIn(f"- Patch ID: `{game}_game_log`", readme)
            self.assertIn(_manifest(game)["description"], readme)
            self.assertIn(f"{game}_game_log", guided)

    def test_the_shipped_dll_exports_only_its_startup(self):
        if not HAVE_PEFILE:
            self.skipTest("pefile not installed")
        pe = pefile.PE(str(DLL))
        names = sorted(e.name.decode() for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name)
        self.assertEqual(names, ["VvfpStartup"])
        imports = {i.name.decode() for e in pe.DIRECTORY_ENTRY_IMPORT for i in e.imports if i.name}
        # (LoadLibraryExW is the static C runtime's own import, as in every companion.)
        self.assertEqual(imports & {"LoadLibraryA", "LoadLibraryW", "LoadLibraryExA",
                                    "DeleteFileA", "DeleteFileW", "OutputDebugStringA"}, set())
        self.assertIn("MoveFileW", imports)
        self.assertIn("SHGetSpecialFolderPathW", imports)
        test_pe = pefile.PE(str(TEST_DLL))
        self.assertIn("VvfpGameLogProbe", {e.name.decode() for e in test_pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name})


@unittest.skipUnless(HAVE_STOCK, NO_STOCK)
class StockExecutables(unittest.TestCase):
    def test_each_writer_is_the_verified_code(self):
        for game in GAMES:
            image = _image(game)
            at = WRITER[game] - IMAGE_BASE
            self.assertEqual(image[at:at + 16].hex().upper(), WRITER_STOCK[game], game)

    def test_every_call_to_the_writer_and_its_line(self):
        for game in GAMES:
            with self.subTest(game=game):
                image = _image(game)
                self.assertEqual(sorted(_direct_calls(image, WRITER[game])), sorted(CALLS[game]))
                for call, fmt in CALLS[game].items():
                    self.assertEqual(_pushed_format(image, call), fmt, f"{game} {call:#x}")
                # the writer is reached only by those calls: no pointer to it, no jump to it
                self.assertNotIn(struct.pack("<I", WRITER[game]), image)

    def test_nothing_branches_into_the_replaced_bytes(self):
        for game in GAMES:
            image = _image(game)
            for target in range(WRITER[game] + 1, WRITER[game] + 6):
                for op in (b"\xE8", b"\xE9"):
                    at = image.find(op, 0x1000)
                    while at != -1 and at < len(image) - 5:
                        rel = struct.unpack_from("<i", image, at + 1)[0]
                        self.assertNotEqual(IMAGE_BASE + at + 5 + rel, target, f"{game} {at + IMAGE_BASE:#x}")
                        at = image.find(op, at + 1)
            # the short jump inside the writer goes past the replaced bytes
            self.assertEqual(image[WRITER[game] - IMAGE_BASE + 11], 0x75)

    def test_the_writers_bytes_survive_every_build_in_every_mode(self):
        for game in GAMES:
            ids = [p.id for p in patcher.load_public_fun_patches()
                   if p.game_id == game and p.id not in patcher.EXPERIMENTAL_FUN_PATCH_IDS]
            self.assertIn(f"{game}_game_log", ids)
            selections = [ids]
            experimental = [p.id for p in patcher.load_public_fun_patches()
                            if p.game_id == game and p.id in patcher.EXPERIMENTAL_FUN_PATCH_IDS]
            if experimental:
                selections.append(ids + experimental)       # the 256 build
            for mode in MODES:
                for selection in selections:
                    with self.subTest(game=game, mode=mode, n=len(selection)):
                        try:
                            data, _ = patcher.render_patched_bytes(STOCK[game], _builds()[game], mode, selection)
                        except patcher.PatcherError as error:
                            if "Expanded" in str(error) or "stock modes only" in str(error):
                                continue
                            raise
                        mapped = _mapped(bytes(data))
                        at = WRITER[game] - IMAGE_BASE
                        self.assertEqual(mapped[at:at + 16].hex().upper(), WRITER_STOCK[game])

    def test_the_row_alone_changes_no_game_code(self):
        for game in GAMES:
            for mode in MODES:
                with self.subTest(game=game, mode=mode):
                    without, _ = patcher.render_patched_bytes(STOCK[game], _builds()[game], mode, [])
                    with_, _ = patcher.render_patched_bytes(STOCK[game], _builds()[game], mode,
                                                            [f"{game}_game_log"])
                    # only the startup loader's own appended section and header fields may differ
                    a, b = _mapped(bytes(without)), _mapped(bytes(with_))
                    text = pefile.PE(data=bytes(without), fast_load=True).sections[0]
                    lo, hi = text.VirtualAddress, text.VirtualAddress + text.Misc_VirtualSize
                    changed = [i for i in range(lo, hi) if a[i] != b[i]]
                    self.assertTrue(all(abs(i - changed[0]) < 16 for i in changed) if changed else True,
                                    [hex(i + IMAGE_BASE) for i in changed[:8]])
                    at = WRITER[game] - IMAGE_BASE
                    self.assertEqual(b[at:at + 16], a[at:at + 16])


@unittest.skipUnless(HAVE_STOCK, NO_STOCK)
class EmulatedGameStart(unittest.TestCase):
    """The published build run from the C runtime's call of WinMain to WinMain
    (tests/startup_emulation.py): VVFP Startup.dll starts VVFP Game Log.dll, which
    replaces the writer's first six bytes and writes the run's first line."""

    def test_each_game_arms_the_writer_and_marks_the_start(self):
        try:
            from startup_emulation import DOCUMENTS
            from test_startup_loader import run
        except ImportError as error:  # pragma: no cover
            self.skipTest(f"emulator unavailable: {error}")
        for game in GAMES:
            for mode in MODES:
                with self.subTest(game=game, mode=mode):
                    machine, _result, _features, _before, _shipped = run(game, mode, (f"{game}_game_log",))
                    code = bytes(machine.code(WRITER[game], 6))
                    self.assertEqual(code[0], 0xE9)
                    self.assertEqual(code[5], 0x90)
                    target = WRITER[game] + 5 + struct.unpack("<i", code[1:5])[0]
                    module = next(m for m in machine.modules.values() if m.base <= target < m.base + m.size)
                    self.assertEqual(module.name.lower(), "vvfp game log.dll")
                    stem = _builds()[game].input_name.split(".")[0]
                    path = f"{DOCUMENTS}\\LDW\\{stem}\\ldwLog.txt"
                    self.assertEqual(machine.files, {path: b"Sun Oct 11 21:05:09 2026: ---- Game started ----\r\n"})


@unittest.skipUnless(CL.is_file(), "the 32-bit MSVC toolchain is not installed")
class Harness(unittest.TestCase):
    def test_the_companions_writer(self):
        with tempfile.TemporaryDirectory(prefix="vvfp_game_log_harness_") as out:
            exe = Path(out) / "game_log_harness.exe"
            build = subprocess.run(
                [str(CL), "/nologo", f"/Fo{out}\\", "/O2", "/MT", "/W4",
                 "/I", str(VS_TOOLS / "include"),
                 "/I", str(SDK / "Include" / SDK_VERSION / "um"),
                 "/I", str(SDK / "Include" / SDK_VERSION / "shared"),
                 "/I", str(SDK / "Include" / SDK_VERSION / "ucrt"),
                 str(NATIVE / "game_log_harness.c"),
                 "/link",
                 f"/LIBPATH:{VS_TOOLS / 'lib' / 'x86'}",
                 f"/LIBPATH:{SDK / 'Lib' / SDK_VERSION / 'um' / 'x86'}",
                 f"/LIBPATH:{SDK / 'Lib' / SDK_VERSION / 'ucrt' / 'x86'}",
                 f"/OUT:{exe}", "kernel32.lib", "shell32.lib"],
                capture_output=True, text=True, cwd=out, timeout=600,
            )
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            self.assertNotIn("warning", build.stdout.lower())
            result = subprocess.run([str(exe)], capture_output=True, text=True, cwd=out, timeout=300)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("== 16 check(s), 0 failure(s) ==", result.stdout)
        self.assertEqual(len(re.findall(r"^  ok ", result.stdout, re.M)), 16, result.stdout)


if __name__ == "__main__":
    unittest.main()
