"""Fix Vanilla Bugs (all five games): the picture no longer freezes when a maximized or full screen game window comes
back from being minimized (the owner, 2026-11-26: "fix the bug that makes the game appear to freeze when a person goes
out of full sceeen and back (includes fully maxed window version)" -- "the screen freezes but the game keeps playing").

* The games: every frame goes through SDL 2.0.3's renderer from one routine the main loop always calls; the event pump
  handles no restore; the full screen toggle is SDL_WINDOW_FULLSCREEN_DESKTOP (static, on the stock executables).
* SDL2.dll 2.0.3 (the games' own file, SHA-256 pinned): the companion's three stock byte checks are SDL's bytes, and
  the harness native/vvfp_window_restore/window_restore_harness.c drives a real SDL window through the real window
  manager on a private desktop: stock, a maximized window and a full screen window made from one come back with the
  renderer hidden (the frozen picture); with the companion's test build every case draws again; with an SDL2.dll that
  differs by one byte the companion installs nothing.  SDL2.dll is not in the repository: these run when it is found
  (VVFP_SDL2_DLL, or SDL2.dll in an inputs/vv<N>-stock-copy folder) and skip otherwise.
* The rows, the release list, the third word and the DLL itself.
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

DLL_NAME = "VVFP Window Restore.dll"
DLL = ROOT / "assets" / "window_restore" / DLL_NAME
TEST_DLL = ROOT / "tests" / "test_dlls" / "VVFP Window Restore.test.dll"
NATIVE = ROOT / "native" / "vvfp_window_restore"
SOURCE = NATIVE / "vvfp_window_restore.c"
HARNESS = NATIVE / "window_restore_harness.c"
STOCK = ROOT / "research" / "stock-executables"
EXES = {1: "Virtual Villagers - A New Home.exe", 2: "Virtual Villagers - The Lost Children.exe",
        3: "Virtual Villagers - The Secret City.exe", 4: "Virtual Villagers - The Tree of Life.exe",
        5: "Virtual Villagers - New Believers.exe"}

VS_TOOLS = Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231")
CL = VS_TOOLS / "bin" / "Hostx64" / "x86" / "cl.exe"
SDK = Path(r"C:\Program Files (x86)\Windows Kits\10")
SDK_VERSION = "10.0.26100.0"

# The SDL2.dll every game ships (FileVersion 2.0.3.0).
SDL_SHA256 = "D197286029C12F95C519BB7F7E41D07C20CA134E66FD7E2B59015ED11551FABD"
# The companion's checks: RVA -> length (native/vvfp_window_restore/vvfp_window_restore.c, WR_CHECKS).
CHECKS = {0xECBF9: 93, 0xEB3B0: 44, 0xBBEC1: 69}
CHANGED_BYTE_RVA = 0xECC19          # the MAXIMIZED event's data1 push (6A 00 -> 6A 01): harmless, but not stock

# Per game: the frame routine, its call in the main loop, the event pump, its call, the full screen toggle.
GAMES = {
    1: (0x403830, 0x409145, 0x403970, 0x40914C, 0x4038B0),
    2: (0x403AC0, 0x409345, 0x403C00, 0x40934C, 0x403B40),
    3: (0x4040E0, 0x409AB5, 0x404220, 0x409ABC, 0x404160),
    4: (0x4046F0, 0x409458, 0x404830, 0x40945F, 0x404770),
    5: (0x404680, 0x409688, 0x4047C0, 0x40968F, 0x404700),
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
    def test_every_fix_vanilla_bugs_row_ships_it_pinned(self) -> None:
        digest = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
        rows = fix_rows()
        self.assertEqual(sorted(rows), [f"vv{g}_fix_vanilla_bugs" for g in range(1, 6)])
        for rid, row in rows.items():
            with self.subTest(row=rid):
                ours = [c for c in row["companion_files"] if c["destination"] == DLL_NAME]
                self.assertEqual(ours, [{"source": f"assets/window_restore/{DLL_NAME}", "destination": DLL_NAME,
                                         "sha256": digest}])
                self.assertIn("The picture no longer freezes when the game window comes back", row["description"])
                self.assertIn(f'("{DLL_NAME}")', row["description"])
                self.assertTrue(row["description"].endswith("**Needs no other patch.**"))
                self.assertEqual(sum(DLL_NAME in b for b in row["behavior_changes"]), 1)
                self.assertEqual(sum(b.startswith("Window Restore writes no byte") for b in
                                     row["explicit_non_changes"]), 1)
                self.assertIn("the frozen picture after a maximized or full screen window comes back",
                              row["evidence_status"])
                # Each row names its own game's routines.
                frame, frame_call, pump, _, toggle = GAMES[int(rid[2])]
                text = next(b for b in row["behavior_changes"] if DLL_NAME in b)
                for va in (frame, frame_call, pump, toggle):
                    self.assertIn(f"0x{va:X}", text)

    def test_the_fix_rows_are_on_by_default(self) -> None:
        public = {p.id: p for p in patcher.load_public_fun_patches()}
        for game in range(1, 6):
            self.assertIn(f"vv{game}_fix_vanilla_bugs", public)

    def test_third_word_release_list_and_header(self) -> None:
        self.assertIn(DLL_NAME, patcher.STARTUP_LOADER_COMPANIONS_3)
        header = (ROOT / "native" / "shared" / "startup_companions_3.h").read_text(encoding="utf-8")
        self.assertIn(f'"{DLL_NAME}",', header)
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        self.assertIn(f'"assets/window_restore/{DLL_NAME}",', release)

    def test_a_fix_row_ships_the_chain_companion_with_it(self) -> None:
        public = {p.id: p for p in patcher.load_public_fun_patches()}
        for game in range(1, 6):
            with self.subTest(game=game):
                rows = patcher._attach_more_companions([public[f"vv{game}_fix_vanilla_bugs"]])
                names = [c["destination"] for f in rows for c in f.raw.get("companion_files", [])]
                self.assertIn(DLL_NAME, names)
                self.assertEqual(names.count("VVFP More Companions.dll"), 1)
                bit = 1 << patcher.STARTUP_LOADER_COMPANIONS_3.index(DLL_NAME)
                self.assertTrue(patcher._startup_loader_mask_3(rows) & bit)


class TheDll(unittest.TestCase):
    def imports(self, path: Path) -> dict[str, set[str]]:
        pe = pefile.PE(str(path))
        return {e.dll.decode().upper(): {i.name.decode() for i in e.imports if i.name}
                for e in pe.DIRECTORY_ENTRY_IMPORT}

    def exports(self, path: Path) -> set[str]:
        pe = pefile.PE(str(path))
        return {s.name.decode() for s in pe.DIRECTORY_ENTRY_EXPORT.symbols if s.name}

    def test_exports(self) -> None:
        self.assertEqual(self.exports(DLL), {"VvfpStartup", "VvfpWindowRestoreInstalled"})
        if TEST_DLL.is_file():
            self.assertEqual(self.exports(TEST_DLL),
                             {"VvfpStartup", "VvfpWindowRestoreInstalled", "VvfpWindowRestoreResyncs"})

    def test_it_writes_no_code_and_only_hooks_messages(self) -> None:
        imports = self.imports(DLL)
        user32 = imports.get("USER32.DLL", set())
        kernel32 = imports.get("KERNEL32.DLL", set())
        self.assertLessEqual({"SetWindowsHookExW", "CallNextHookEx", "GetPropW", "SendMessageW"}, user32)
        self.assertLessEqual({"GetModuleHandleA", "GetProcAddress", "GetCurrentThreadId"}, kernel32)
        self.assertLessEqual(set(imports), {"USER32.DLL", "KERNEL32.DLL"})
        # (the static C runtime imports VirtualProtect, CreateFileW ... for itself: the companion's own code is
        # held to it by its source)
        text = SOURCE.read_text(encoding="utf-8")
        for never in ("VirtualProtect", "WriteProcessMemory", "VirtualAlloc", "CreateFile", "WriteFile",
                      "OutputDebugString", "install_sites.h", "printf", "MessageBox"):
            self.assertNotIn(never, text)

    def test_the_source_names_what_it_waits_for(self) -> None:
        text = SOURCE.read_text(encoding="utf-8")
        self.assertIn('#define WR_SDL_PROP L"SDL_WindowData"', text)
        self.assertIn("SetWindowsHookExW(WH_CALLWNDPROC, wr_hook, NULL, GetCurrentThreadId())", text)
        self.assertIn("kind == SIZE_MAXIMIZED && g_minimized == window && !g_inside", text)
        self.assertIn("SendMessageW(window, WM_SIZE, SIZE_RESTORED, size);", text)
        self.assertIn("version.major != 2 || version.minor != 0 || version.patch != 3", text)
        checks = re.findall(r"\{0x([0-9A-F]+)u, \(unsigned int\)sizeof (\w+), \w+\}", text)
        self.assertEqual({int(rva, 16): len(c_bytes(name)) for rva, name in checks}, CHECKS)


@unittest.skipUnless(all((STOCK / exe).is_file() for exe in EXES.values()), "stock executables not present")
class TheGames(unittest.TestCase):
    """Every game presents each frame through SDL from one routine its main loop always calls."""

    def image(self, game: int) -> tuple[pefile.PE, bytes, dict[str, int]]:
        pe = pefile.PE(str(STOCK / EXES[game]))
        image = pe.get_memory_mapped_image()
        iat = {i.name.decode(): i.address for e in pe.DIRECTORY_ENTRY_IMPORT if e.dll.decode().upper() == "SDL2.DLL"
               for i in e.imports if i.name}
        return pe, image, iat

    def thunk(self, image: bytes, iat: int) -> int:
        at = image.find(b"\xff\x25" + struct.pack("<I", iat), 0x1000)
        self.assertGreater(at, 0)
        return 0x400000 + at

    def calls_in(self, image: bytes, start: int, length: int) -> list[int]:
        out = []
        for at in range(start - 0x400000, start - 0x400000 + length):
            if image[at] == 0xE8:
                out.append((0x400000 + at + 5 + struct.unpack_from("<i", image, at + 1)[0]) & 0xFFFFFFFF)
        return out

    def test_frames_go_through_sdl_every_pass(self) -> None:
        for game, (frame, frame_call, pump, pump_call, _) in GAMES.items():
            with self.subTest(game=game):
                _, image, iat = self.image(game)
                order = [self.thunk(image, iat[n]) for n in
                         ("SDL_UpdateTexture", "SDL_RenderClear", "SDL_RenderCopy", "SDL_RenderPresent")]
                calls = self.calls_in(image, frame, 0x40)
                self.assertEqual([c for c in calls if c in order], order)
                for call, target in ((frame_call, frame), (pump_call, pump)):
                    at = call - 0x400000
                    self.assertEqual(image[at], 0xE8)
                    self.assertEqual((call + 5 + struct.unpack_from("<i", image, at + 1)[0]) & 0xFFFFFFFF, target)
                # The frame call and the pump call follow one another with nothing that could skip the frame.
                self.assertEqual(pump_call - frame_call, 7)                 # call frame / mov ecx, esi / call pump
                self.assertEqual(image[frame_call - 0x400000 + 5:frame_call - 0x400000 + 7], b"\x8b\xce")

    def test_the_pump_handles_no_restore(self) -> None:
        for game, (_, _, pump, _, _) in GAMES.items():
            with self.subTest(game=game):
                _, image, _ = self.image(game)
                body = image[pump - 0x400000:pump - 0x400000 + 0x400]
                # SDL_WINDOWEVENT (0x200) is one case (cmp eax, 0x200 / je), and it tests only event 5 (RESIZED):
                # cmp byte ptr [esp + x], 5 / jne the end of the loop.
                cases = [m for m in re.finditer(rb"\x3d\x00\x02\x00\x00\x0f\x84(.{4})", body, flags=re.S)]
                self.assertEqual(len(cases), 1)
                case = cases[0]
                target = pump - 0x400000 + case.end() + struct.unpack("<i", case.group(1))[0]
                self.assertEqual(image[target:target + 3], b"\x80\x7c\x24")
                self.assertEqual(image[target + 4:target + 7], b"\x05\x0f\x85")

    def test_full_screen_is_full_screen_desktop(self) -> None:
        for game, (_, _, _, _, toggle) in GAMES.items():
            with self.subTest(game=game):
                _, image, iat = self.image(game)
                body = image[toggle - 0x400000:toggle - 0x400000 + 0xC0]
                self.assertIn(b"\x68\x01\x10\x00\x00", body)                   # push 0x1001
                self.assertIn(self.thunk(image, iat["SDL_SetWindowFullscreen"]), self.calls_in(image, toggle, 0xC0))


@unittest.skipUnless(sdl2_dll() is not None, "the games' SDL2.dll (2.0.3) is not on this machine")
class TheSdlBytes(unittest.TestCase):
    def test_the_companions_checks_are_sdl_203s_bytes(self) -> None:
        pe = pefile.PE(str(sdl2_dll()))
        image = pe.get_memory_mapped_image()
        for rva, name in ((0xECBF9, "WR_WM_SIZE"), (0xEB3B0, "WR_MAXIMIZED"), (0xBBEC1, "WR_RENDER_WATCH")):
            with self.subTest(name=name):
                self.assertEqual(image[rva:rva + CHECKS[rva]], c_bytes(name))
        # The changed copy the harness refuses differs inside the first check.
        self.assertTrue(0xECBF9 <= CHANGED_BYTE_RVA < 0xECBF9 + CHECKS[0xECBF9])
        self.assertEqual(image[CHANGED_BYTE_RVA - 1:CHANGED_BYTE_RVA + 1], b"\x6a\x00")


@unittest.skipUnless(CL.is_file(), "the 32-bit MSVC toolchain is not installed")
@unittest.skipUnless(sdl2_dll() is not None, "the games' SDL2.dll (2.0.3) is not on this machine")
@unittest.skipUnless(TEST_DLL.is_file(), "the companion's test build is not present")
class RealSdl(unittest.TestCase):
    """The harness, with the games' own SDL2.dll, on a private desktop."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory(prefix="vvfp_wr_")
        out = Path(cls.tmp.name)
        cls.exe = out / "window_restore_harness.exe"
        build = subprocess.run(
            [str(CL), "/nologo", f"/Fo{out}\\", "/O2", "/MT", "/W4",
             "/I", str(VS_TOOLS / "include"),
             "/I", str(SDK / "Include" / SDK_VERSION / "um"),
             "/I", str(SDK / "Include" / SDK_VERSION / "shared"),
             "/I", str(SDK / "Include" / SDK_VERSION / "ucrt"),
             str(HARNESS), "/link",
             f"/LIBPATH:{VS_TOOLS / 'lib' / 'x86'}",
             f"/LIBPATH:{SDK / 'Lib' / SDK_VERSION / 'um' / 'x86'}",
             f"/LIBPATH:{SDK / 'Lib' / SDK_VERSION / 'ucrt' / 'x86'}",
             f"/OUT:{cls.exe}", "user32.lib"],
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
        data[pe.get_offset_from_rva(CHANGED_BYTE_RVA)] = 0x01
        (cls.changed_sdl / "SDL2.dll").write_bytes(bytes(data))
        cls.dll = out / TEST_DLL.name
        shutil.copy2(TEST_DLL, cls.dll)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def run_harness(self, mode: str) -> str:
        folder = self.changed_sdl if mode == "refused" else self.stock_sdl
        args = [str(self.exe), str(folder), mode] + ([] if mode == "stock" else [str(self.dll)])
        result = subprocess.run(args, capture_output=True, text=True, timeout=300)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("\nFAIL ", "\n" + result.stdout)
        return result.stdout

    def test_stock_freezes_a_maximized_window_and_full_screen_made_from_one(self) -> None:
        out = self.run_harness("stock")
        for line in ("ok B. stock: the maximized window comes back frozen",
                     "ok B. stock: still frozen after a click away and back",
                     "ok B. a window no longer maximized draws (the stock way out)",
                     "ok D. stock: back in full screen, frozen",
                     "ok D. stock: SDL thinks it is still minimized, so it is not minimized again",
                     "ok D. stock: still frozen in full screen",
                     "ok A. a window draws again when it comes back",
                     "ok C. back in full screen, drawing (stock SDL, both runs)",
                     "ok E. back in full screen, drawing (stock SDL, both runs)"):
            self.assertIn(line, out)
        self.assertIn("== 18 check(s), 0 failure(s) ==", out)

    def test_with_the_companion_nothing_freezes(self) -> None:
        out = self.run_harness("fixed")
        for line in ("ok companion installed with the stock SDL 2.0.3",
                     "ok B. the maximized window draws again when it comes back",
                     "ok B. SDL counts it maximized, not minimized",
                     "ok B. still drawing after a click away and back",
                     "ok D. back in full screen, drawing",
                     "ok D. back over the whole screen (SDL put full screen back)",
                     "ok D. the next alt-tab minimizes it again",
                     "ok D. back again, drawing over the whole screen",
                     "ok D. out of full screen: the maximized window, drawing",
                     "ok A. a window draws again when it comes back",
                     "ok C. and again",
                     "ok E. back in full screen, drawing (stock SDL, both runs)",
                     "ok only B and D's two returns needed the companion"):
            self.assertIn(line, out)
        self.assertIn("== 22 check(s), 0 failure(s) ==", out)

    def test_another_sdl2_dll_installs_nothing(self) -> None:
        out = self.run_harness("refused")
        self.assertIn("ok companion refuses a changed SDL2.dll", out)
        self.assertIn("ok D. stock: still frozen in full screen", out)
        self.assertIn("ok the refused companion never acted", out)
        self.assertIn("== 19 check(s), 0 failure(s) ==", out)


if __name__ == "__main__":
    unittest.main()
