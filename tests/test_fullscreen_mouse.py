"""Fix Vanilla Bugs (all five games): the mouse works in full screen and in a game window bigger than the game's
picture (the owner, 2026-11-26: "go ahead" on the stock full screen mouse offset).

* The games: each event pump reads SDL_GetMouseState, through the game's import, on every move, left press and
  release, and hands those numbers on as its own (static, on the stock executables).
* SDL2.dll 2.0.3 (the games' own file, SHA-256 pinned): the companion's checks are SDL's bytes; and the harness
  native/vvfp_fullscreen_mouse/fullscreen_mouse_harness.c maps each stock executable into its process, runs the
  game's OWN event pump as machine code with the real SDL2.dll driving a real window on a private desktop, and
  compares what the game receives with the picture's pixel under the pointer: stock, the game reads window pixels
  whenever the window is bigger than its picture (a 1.5x window, a wide window with bars, full screen); with the
  companion's test build it reads the picture's pixel exactly every time, and the warp's reverse conversion lands on
  the same pixel; with an SDL2.dll that differs by one byte the companion installs nothing.  SDL2.dll is not in the
  repository: these run when it is found (VVFP_SDL2_DLL, or SDL2.dll in an inputs/vv<N>-stock-copy folder) and skip
  otherwise.
* The rows, the release list, the start from Window Restore, and Show Parents reading through the game's import.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pefile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as patcher  # noqa: E402

DLL_NAME = "VVFP Fullscreen Mouse.dll"
DLL = ROOT / "assets" / "fullscreen_mouse" / DLL_NAME
TEST_DLL = ROOT / "tests" / "test_dlls" / "VVFP Fullscreen Mouse.test.dll"
NATIVE = ROOT / "native" / "vvfp_fullscreen_mouse"
SOURCE = NATIVE / "vvfp_fullscreen_mouse.c"
HARNESS = NATIVE / "fullscreen_mouse_harness.c"
RESTORE_SOURCE = ROOT / "native" / "vvfp_window_restore" / "vvfp_window_restore.c"
RESTORE_DLL = ROOT / "assets" / "window_restore" / "VVFP Window Restore.dll"
PARENTAGE_SOURCE = ROOT / "native" / "vv1_parentage" / "vv1_parentage.c"
STOCK = ROOT / "research" / "stock-executables"
EXES = {1: "Virtual Villagers - A New Home.exe", 2: "Virtual Villagers - The Lost Children.exe",
        3: "Virtual Villagers - The Secret City.exe", 4: "Virtual Villagers - The Tree of Life.exe",
        5: "Virtual Villagers - New Believers.exe"}

VS_TOOLS = Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231")
CL = VS_TOOLS / "bin" / "Hostx64" / "x86" / "cl.exe"
SDK = Path(r"C:\Program Files (x86)\Windows Kits\10")
SDK_VERSION = "10.0.26100.0"

SDL_SHA256 = "D197286029C12F95C519BB7F7E41D07C20CA134E66FD7E2B59015ED11551FABD"
# The companion's checks: RVA -> length (FM_WATCH, FM_WATCH_Y).
CHECKS = {0xBBF0B: 88, 0xBBF6E: 15}
CHANGED_BYTE_RVA = 0xBBF23        # cmp dword ptr [edx+0xC4], 0 -> 1: the same while a logical size is set

# Per game: picture size, event pump, its three SDL_GetMouseState calls, the input manager routine, the frame
# routine's SDL_WarpMouseInWindow call.
GAMES = {
    1: ((800, 600), 0x403970, (0x403BFC, 0x403C2B, 0x403C53), 0x401F60, 0x40388E),
    2: ((800, 600), 0x403C00, (0x403E8C, 0x403EBB, 0x403EE3), 0x401FF0, 0x403B1E),
    3: ((800, 600), 0x404220, (0x4044AC, 0x4044DB, 0x404503), 0x402020, 0x40413E),
    4: ((800, 600), 0x404830, (0x404A90, 0x404ABF, 0x404AE7), 0x402250, 0x40474E),
    5: ((1024, 768), 0x4047C0, (0x404A20, 0x404A4F, 0x404A77), 0x402200, 0x4046DE),
}


def sdl2_dll() -> Path | None:
    """The games' SDL2.dll, when this machine has it (never part of the repository)."""
    candidates = []
    if os.environ.get("VVFP_SDL2_DLL"):
        candidates.append(Path(os.environ["VVFP_SDL2_DLL"]))
    candidates += sorted((ROOT / "inputs").glob("vv*-stock-copy/SDL2.dll"))
    for path in candidates:
        if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest().upper() == SDL_SHA256:
            return path
    return None


def fix_rows() -> dict[str, dict]:
    data = json.loads((ROOT / "data" / "builds.json").read_text(encoding="utf-8"))
    return {row["id"]: row for row in data["fun_patches"] if str(row.get("id", "")).endswith("_fix_vanilla_bugs")}


def c_bytes(name: str) -> bytes:
    text = SOURCE.read_text(encoding="utf-8")
    body = text[text.index(f"static const unsigned char {name}[] = {{"):]
    body = body[body.index("{") + 1:body.index("};")]
    return bytes(int(v, 16) for v in re.findall(r"0x([0-9A-Fa-f]{2})", body))


class TheRows(unittest.TestCase):
    def test_every_fix_vanilla_bugs_row_ships_it_pinned_after_window_restore(self) -> None:
        digest = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
        rows = fix_rows()
        self.assertEqual(sorted(rows), [f"vv{g}_fix_vanilla_bugs" for g in range(1, 6)])
        for rid, row in rows.items():
            with self.subTest(row=rid):
                names = [c["destination"] for c in row["companion_files"]]
                ours = [c for c in row["companion_files"] if c["destination"] == DLL_NAME]
                self.assertEqual(ours, [{"source": f"assets/fullscreen_mouse/{DLL_NAME}", "destination": DLL_NAME,
                                         "sha256": digest}])
                # Window Restore starts it: always shipped together.
                self.assertIn("VVFP Window Restore.dll", names)
                self.assertIn("The mouse now works in full screen", row["description"])
                self.assertIn(f'("{DLL_NAME}")', row["description"])
                self.assertTrue(row["description"].endswith("**Needs no other patch.**"))
                self.assertEqual(sum(DLL_NAME in b for b in row["behavior_changes"]), 1)
                self.assertEqual(sum(b.startswith("Fullscreen Mouse writes no byte") for b in
                                     row["explicit_non_changes"]), 1)
                self.assertIn("the mouse in full screen and in bigger windows", row["evidence_status"])
                (_, pump, sites, _, warp) = GAMES[int(rid[2])]
                text = next(b for b in row["behavior_changes"] if DLL_NAME in b)
                for va in (pump, warp) + sites:
                    self.assertIn(f"0x{va:X}", text)

    def test_the_release_list_ships_it(self) -> None:
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        self.assertIn(f'"assets/fullscreen_mouse/{DLL_NAME}",', release)
        # Started by Window Restore, not by a startup word of its own.
        self.assertNotIn(DLL_NAME, patcher.STARTUP_LOADER_COMPANIONS_3)
        for header in (ROOT / "native" / "shared").glob("startup_companions*.h"):
            self.assertNotIn(DLL_NAME, header.read_text(encoding="utf-8"))

    def test_the_guide_says_it_plainly(self) -> None:
        guides = json.loads((ROOT / "data" / "how_to_use.json").read_text(encoding="utf-8"))
        text = json.dumps(guides)
        self.assertEqual(text.count("the mouse clicks exactly where the pointer is"), 5)


class TheDll(unittest.TestCase):
    def imports(self, path: Path) -> dict[str, set[str]]:
        pe = pefile.PE(str(path))
        return {e.dll.decode().upper(): {i.name.decode() for i in e.imports if i.name}
                for e in pe.DIRECTORY_ENTRY_IMPORT}

    def exports(self, path: Path) -> set[str]:
        pe = pefile.PE(str(path))
        return {s.name.decode() for s in pe.DIRECTORY_ENTRY_EXPORT.symbols if s.name}

    def test_exports(self) -> None:
        self.assertEqual(self.exports(DLL), {"VvfpStartup", "VvfpFullscreenMouseInstalled"})
        if TEST_DLL.is_file():
            self.assertEqual(self.exports(TEST_DLL), {"VvfpStartup", "VvfpFullscreenMouseInstalled",
                                                      "VvfpFullscreenMouseTestUseModule",
                                                      "VvfpFullscreenMouseTestConvert"})

    def test_it_changes_only_three_import_entries(self) -> None:
        self.assertLessEqual(set(self.imports(DLL)), {"KERNEL32.DLL"})
        text = SOURCE.read_text(encoding="utf-8")
        for never in ("WriteProcessMemory", "VirtualAlloc", "CreateFile", "WriteFile", "OutputDebugString",
                      "printf", "MessageBox", "SetWindowsHookEx", "install_sites.h"):
            self.assertNotIn(never, text)
        # VirtualProtect only around an import table entry, and exactly three entries, by name, of SDL2.dll.
        self.assertEqual(text.count("VirtualProtect("), 2)
        self.assertEqual(re.findall(r'fm_import\(module, "(\w+)"\)', text),
                         ["SDL_CreateRenderer", "SDL_GetMouseState", "SDL_WarpMouseInWindow"])
        self.assertEqual(text.count("fm_set("), 4)   # the definition and three calls
        self.assertIn("version.major != 2 || version.minor != 0 || version.patch != 3", text)

    def test_the_conversion_is_sdls_own(self) -> None:
        text = SOURCE.read_text(encoding="utf-8")
        for define in ("#define FM_LOGICAL_W 0xC4", "#define FM_VIEWPORT_X 0xD4", "#define FM_VIEWPORT_Y 0xD8",
                       "#define FM_SCALE_X 0x114", "#define FM_SCALE_Y 0x118", "#define FM_WATCH_RVA 0xBBF0Bu",
                       "#define FM_WATCH_Y_RVA 0xBBF6Eu"):
            self.assertIn(define, text)
        self.assertEqual(len(c_bytes("FM_WATCH")), CHECKS[0xBBF0B])
        self.assertEqual(len(c_bytes("FM_WATCH_Y")), CHECKS[0xBBF6E])
        table = re.findall(r"\{(0x[0-9A-F]+), (0x[0-9A-F]+), (0x[0-9A-F]+)\}", text)
        self.assertEqual([tuple(int(v, 16) for v in row) for row in table], [GAMES[g][2] for g in range(1, 6)])

    def test_window_restore_starts_it_by_its_full_path(self) -> None:
        text = RESTORE_SOURCE.read_text(encoding="utf-8")
        self.assertIn('#include "../shared/patcher_files.h"', text)
        self.assertIn('vvfp_load_patcher_dll("VVFP Fullscreen Mouse.dll")', text)
        start = text[text.index("void __stdcall VvfpStartup(int game, unsigned int shipped) {"):]
        # before Window Restore's own SDL check, so a refused Window Restore does not hold it back
        self.assertLess(start.index("wr_start_fullscreen_mouse(game, shipped);"), start.index("wr_sdl_is_stock()"))
        imports = TheDll.imports(self, RESTORE_DLL)
        self.assertIn("LoadLibraryExW", imports["KERNEL32.DLL"])
        self.assertLessEqual(set(imports), {"USER32.DLL", "KERNEL32.DLL"})

    def test_show_parents_reads_through_the_games_import(self) -> None:
        text = PARENTAGE_SOURCE.read_text(encoding="utf-8")
        body = text[text.index("static int vv1_mouse(int *x, int *y) {"):]
        body = body[:body.index("\n}\n")]
        self.assertIn('g_mouse_import = vv1_game_import("SDL_GetMouseState");', body)
        self.assertIn("(through_game != NULL ? through_game : g_mouse)(x, y);", body)


@unittest.skipUnless(all((STOCK / exe).is_file() for exe in EXES.values()), "stock executables not present")
class TheGames(unittest.TestCase):
    """Every game's pump reads the mouse from SDL_GetMouseState, through its import, never from the event."""

    def image(self, game: int) -> tuple[bytes, dict[str, int]]:
        pe = pefile.PE(str(STOCK / EXES[game]))
        image = pe.get_memory_mapped_image()
        iat = {i.name.decode(): i.address for e in pe.DIRECTORY_ENTRY_IMPORT if e.dll.decode().upper() == "SDL2.DLL"
               for i in e.imports if i.name}
        return image, iat

    def target(self, image: bytes, call: int) -> int:
        at = call - 0x400000
        self.assertEqual(image[at], 0xE8)
        return (call + 5 + struct.unpack_from("<i", image, at + 1)[0]) & 0xFFFFFFFF

    def thunk_slot(self, image: bytes, thunk: int) -> int:
        at = thunk - 0x400000
        self.assertEqual(image[at:at + 2], b"\xff\x25")
        return struct.unpack_from("<I", image, at + 2)[0]

    def test_the_pump_reads_sdl_getmousestate_through_the_import(self) -> None:
        for game, (_, pump, sites, manager, warp) in GAMES.items():
            with self.subTest(game=game):
                image, iat = self.image(game)
                for site in sites:
                    self.assertEqual(self.thunk_slot(image, self.target(image, site)), iat["SDL_GetMouseState"])
                    # push the y, push the x it got back, push the kind: the numbers go on unchanged
                    after = image[site - 0x400000 + 5:site - 0x400000 + 0x20]
                    self.assertIn(b"\x83\xc4\x08", after)                         # add esp, 8
                self.assertEqual(self.thunk_slot(image, self.target(image, warp)), iat["SDL_WarpMouseInWindow"])
                # the stock input-manager routine starts with push -1 (the harness's stand-in replaces it)
                self.assertEqual(image[manager - 0x400000:manager - 0x400000 + 2], b"\x6a\xff")
                # the three cases: SDL_MOUSEMOTION (0x400), BUTTONDOWN (0x401), BUTTONUP (0x402) in the pump
                body = image[pump - 0x400000:pump - 0x400000 + 0x400]
                self.assertIn(b"\x2d\x00\x04\x00\x00", body)                       # sub eax, 0x400

    def test_the_window_has_a_logical_size(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                image, iat = self.image(game)
                needle = b"\xff\x25" + struct.pack("<I", iat["SDL_RenderSetLogicalSize"])
                self.assertGreater(image.find(needle, 0x1000), 0)


@unittest.skipUnless(sdl2_dll() is not None, "the games' SDL2.dll (2.0.3) is not on this machine")
class TheSdlBytes(unittest.TestCase):
    def test_the_companions_checks_are_sdl_203s_bytes(self) -> None:
        image = pefile.PE(str(sdl2_dll())).get_memory_mapped_image()
        self.assertEqual(image[0xBBF0B:0xBBF0B + 88], c_bytes("FM_WATCH"))
        self.assertEqual(image[0xBBF6E:0xBBF6E + 15], c_bytes("FM_WATCH_Y"))
        self.assertTrue(0xBBF0B <= CHANGED_BYTE_RVA < 0xBBF0B + 88)
        self.assertEqual(image[CHANGED_BYTE_RVA - 6:CHANGED_BYTE_RVA + 1], b"\x83\xba\xc4\x00\x00\x00\x00")


@unittest.skipUnless(CL.is_file(), "the 32-bit MSVC toolchain is not installed")
@unittest.skipUnless(sdl2_dll() is not None, "the games' SDL2.dll (2.0.3) is not on this machine")
@unittest.skipUnless(TEST_DLL.is_file(), "the companion's test build is not present")
@unittest.skipUnless(all((STOCK / exe).is_file() for exe in EXES.values()), "stock executables not present")
class RealSdl(unittest.TestCase):
    """The harness: each game's own event pump, the games' own SDL2.dll, a real window on a private desktop."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory(prefix="vvfp_fm_")
        out = Path(cls.tmp.name)
        cls.exe = out / "fullscreen_mouse_harness.exe"
        build = subprocess.run(
            [str(CL), "/nologo", f"/Fo{out}\\", "/O2", "/MT", "/W4", "/D_CRT_SECURE_NO_WARNINGS",
             "/I", str(VS_TOOLS / "include"),
             "/I", str(SDK / "Include" / SDK_VERSION / "um"),
             "/I", str(SDK / "Include" / SDK_VERSION / "shared"),
             "/I", str(SDK / "Include" / SDK_VERSION / "ucrt"),
             str(HARNESS), "/link",
             # the harness stays clear of 0x400000, where the game's own executable goes
             "/BASE:0x30000000", "/DYNAMICBASE:NO",
             f"/LIBPATH:{VS_TOOLS / 'lib' / 'x86'}",
             f"/LIBPATH:{SDK / 'Lib' / SDK_VERSION / 'um' / 'x86'}",
             f"/LIBPATH:{SDK / 'Lib' / SDK_VERSION / 'ucrt' / 'x86'}",
             f"/OUT:{cls.exe}", "user32.lib", "shell32.lib", "ole32.lib"],
            capture_output=True, text=True, cwd=out, timeout=600)
        if build.returncode != 0:
            raise AssertionError(build.stdout + build.stderr)
        cls.stock_sdl = out / "sdl"
        cls.stock_sdl.mkdir()
        shutil.copy2(sdl2_dll(), cls.stock_sdl / "SDL2.dll")
        cls.changed_sdl = out / "sdl_changed"
        cls.changed_sdl.mkdir()
        data = bytearray((cls.stock_sdl / "SDL2.dll").read_bytes())
        pe = pefile.PE(data=bytes(data), fast_load=True)
        offset = pe.get_offset_from_rva(CHANGED_BYTE_RVA)
        assert data[offset] == 0
        data[offset] = 0x01
        (cls.changed_sdl / "SDL2.dll").write_bytes(bytes(data))
        cls.dll = out / TEST_DLL.name
        shutil.copy2(TEST_DLL, cls.dll)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def run_harness(self, game: int, mode: str) -> str:
        folder = self.changed_sdl if mode == "refused" else self.stock_sdl
        args = [str(self.exe), str(folder), str(STOCK / EXES[game]), str(game), mode]
        if mode != "stock":
            args.append(str(self.dll))
        result = subprocess.run(args, capture_output=True, text=True, timeout=300)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("\nFAIL ", "\n" + result.stdout)
        return result.stdout

    def test_stock_the_game_reads_window_pixels(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                out = self.run_harness(game, "stock")
                self.assertIn("ok A. a window of the picture's own size: stock, a window of the picture's own size is "
                              "right", out)
                for state in ("B. a window 1.5 times the picture", "C. a wide window (black bars at the sides)",
                              "D. full screen (the game's own full screen, 0x1001)"):
                    self.assertRegex(out, re.escape(f"ok {state}: stock, the game reads window pixels, off by up to ")
                                     + r"[1-9]\d* picture pixels")
                self.assertIn("ok E. back to a window of the picture's own size: stock, a window of the picture's "
                              "own size is right", out)
                self.assertIn("== 11 check(s), 0 failure(s) ==", out)

    def test_with_the_companion_the_game_reads_the_pictures_pixel(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                out = self.run_harness(game, "fixed")
                self.assertIn("ok companion installed with the stock SDL 2.0.3 and game", out)
                for state in ("A. a window of the picture's own size", "B. a window 1.5 times the picture",
                              "C. a wide window (black bars at the sides)",
                              "D. full screen (the game's own full screen, 0x1001)",
                              "E. back to a window of the picture's own size"):
                    self.assertIn(f"ok {state}: the game's pump received every move, press and release (27)", out)
                    self.assertIn(f"ok {state}: the game reads the picture's pixel under the pointer, exactly", out)
                    self.assertIn(f"ok {state}: the pointer warp lands on the same picture pixel (game -> window -> "
                                  "game)", out)
                self.assertIn("== 16 check(s), 0 failure(s) ==", out)

    def test_another_sdl2_dll_installs_nothing(self) -> None:
        for game in (1, 5):
            with self.subTest(game=game):
                out = self.run_harness(game, "refused")
                self.assertIn("ok companion refuses a changed SDL2.dll", out)
                self.assertIn("ok D. full screen (the game's own full screen, 0x1001): stock, the game reads window "
                              "pixels", out)
                self.assertIn("== 11 check(s), 0 failure(s) ==", out)


if __name__ == "__main__":
    unittest.main()
