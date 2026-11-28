"""Sharp Full Screen Picture (4K Filter) (New Believers first; the owner, 2026-11-26/27): "VVFP Sharp Picture.dll".

* The row: off by default (Owner's Defaults ticks it), says to use it with Fix Vanilla Bugs, ships the DLL pinned,
  started from the third word (bit 23); its Settings window: black bars (default) or stretch.
* The DLL: its exports, its imports (no Direct3D import and no DLL loaded: it uses the d3d9.dll SDL's renderer
  loaded), nothing written but its import entries, the shaders compiled in, no file but its settings file read.
* The harness native/vvfp_sharp_picture/sharp_picture_harness.c (with the games' SDL2.dll, when present): the game's
  own frame routine draws through the companion; the picture equals the CPU reference of the filter in a window and a
  screen-wide window, in bars and stretch; a click on a bar is dropped; a changed frame routine installs nothing.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pefile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as patcher  # noqa: E402

DLL_NAME = "VVFP Sharp Picture.dll"
DLL = ROOT / "assets" / "sharp_picture" / DLL_NAME
TEST_DLL = ROOT / "tests" / "test_dlls" / "VVFP Sharp Picture.test.dll"
NATIVE = ROOT / "native" / "vvfp_sharp_picture"
SOURCE = NATIVE / "vvfp_sharp_picture.c"
HARNESS = NATIVE / "sharp_picture_harness.c"
FILTERS = ROOT / "native" / "vvfp_4k_filter" / "vv4k_filters.c"
ROW = ROOT / "data" / "vv5_sharp_picture_feature.json"
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - New Believers.exe"
SDL_SHA256 = "D197286029C12F95C519BB7F7E41D07C20CA134E66FD7E2B59015ED11551FABD"
VS_TOOLS = Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231")
CL = VS_TOOLS / "bin" / "Hostx64" / "x86" / "cl.exe"
SDK = Path(r"C:\Program Files (x86)\Windows Kits\10")
SDK_VERSION = "10.0.26100.0"


def sdl2_dll() -> Path | None:
    candidates = [Path(os.environ["VVFP_SDL2_DLL"])] if os.environ.get("VVFP_SDL2_DLL") else []
    candidates += sorted((ROOT / "inputs").glob("vv*-stock-copy/SDL2.dll"))
    for path in candidates:
        if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest().upper() == SDL_SHA256:
            return path
    return None


class TheRow(unittest.TestCase):
    def test_the_row(self) -> None:
        row = json.loads(ROW.read_text(encoding="utf-8"))
        self.assertEqual(row["id"], "vv5_sharp_picture")
        self.assertEqual(row["dependencies"], [])
        self.assertIn("**Use it with Fix Vanilla Bugs**", row["description"])
        self.assertEqual(row["companion_files"], [{"source": f"assets/sharp_picture/{DLL_NAME}",
                                                   "destination": DLL_NAME,
                                                   "sha256": hashlib.sha256(DLL.read_bytes()).hexdigest().upper()}])
        self.assertEqual(row["patches"], [])

    def test_third_word_bit_23_and_off_by_default(self) -> None:
        self.assertEqual(patcher.STARTUP_LOADER_COMPANIONS_3.index(DLL_NAME), 23)
        header = (ROOT / "native" / "shared" / "startup_companions_3.h").read_text(encoding="utf-8")
        names = re.findall(r'^\s+"(VVFP [^"]+\.dll)",', header, re.M)
        self.assertEqual(names.index(DLL_NAME), 23)
        import vv_fun_patcher_gui as gui
        self.assertIn("vv5_sharp_picture", gui.DEFAULT_OFF_FUN_PATCH_IDS)
        # Owner's Defaults ticks it (the owner, 2026-11-28), as every default-off row it does not hold back;
        # Select All follows the same rule.
        self.assertNotIn("vv5_sharp_picture", gui.OWNERS_DEFAULT_OFF_FUN_PATCH_IDS)
        self.assertNotIn("vv5_sharp_picture", gui.SELECT_ALL_OFF_FUN_PATCH_IDS)
        self.assertIn(f'"assets/sharp_picture/{DLL_NAME}",', (ROOT / "scripts" / "build_release.py").read_text(
            encoding="utf-8"))


class TheSettings(unittest.TestCase):
    """Black bars or stretch (the owner, 2026-11-27): the row's Settings window, the file beside the companion."""

    def tearDown(self) -> None:
        patcher.set_sharp_picture_fit("bars")

    def test_the_settings_window(self) -> None:
        import vv_fun_patcher_gui as gui
        self.assertEqual(gui.PATCH_SETTINGS_ROWS["sharp_picture"], ("_fill_sharp_picture_settings",
                                                                     ("sharp_picture_fit",)))
        self.assertTrue(callable(getattr(gui.App, "_fill_sharp_picture_settings")))
        rows = json.loads((ROOT / "data" / "translations" / "patcher_strings.json").read_text(encoding="utf-8"))
        english = {r["stem"]: r["english"] for r in rows["strings"]}
        for name, text in zip(("intro", "bars", "stretch"), gui.SHARP_PICTURE_SETTINGS_TEXTS):
            self.assertEqual(english[f"vvfp.gui/sharp_picture.{name}"], text)
        import vv_how_to_use
        self.assertIn("Black bars (the default)", " ".join(vv_how_to_use.guide("sharp_picture_fit").lines))

    def test_the_choice_and_the_file(self) -> None:
        self.assertEqual(patcher.SHARP_PICTURE_FIT_DEFAULT, "bars")
        self.assertEqual(patcher.sharp_picture_fit(), "bars")
        with self.assertRaises(patcher.PatcherError):
            patcher.set_sharp_picture_fit("zoom")
        row = next(p for p in patcher.load_public_fun_patches() if p.id == "vv5_sharp_picture")
        for fit in ("bars", "stretch"):
            with self.subTest(fit=fit), tempfile.TemporaryDirectory() as folder:
                patcher.set_sharp_picture_fit(fit)
                patcher._write_sharp_picture_choice(Path(folder), [row])
                written = list(Path(folder).rglob(patcher.SHARP_PICTURE_FILE))
                self.assertEqual(len(written), 1)
                self.assertEqual(written[0].read_text(encoding="ascii"), fit + "\n")
                self.assertEqual(written[0].parent.name, "Virtual Villagers Fun Patcher Files")
        with tempfile.TemporaryDirectory() as folder:   # a build without the row writes nothing
            patcher._write_sharp_picture_choice(Path(folder), [])
            self.assertEqual(list(Path(folder).rglob("*")), [])
        self.assertIn(patcher.SHARP_PICTURE_FILE, (ROOT / "src" / "patcher_files.py").read_text(encoding="utf-8"))
        args = patcher._parser().parse_args(["dry-run", "x.exe", "--sharp-picture-fit", "stretch"])
        self.assertEqual(args.sharp_picture_fit, "stretch")
        # the companion reads "stretch", anything else is bars
        self.assertIn('g_stretch = strstr(text, "stretch") != NULL;', SOURCE.read_text(encoding="utf-8"))


class TheDll(unittest.TestCase):
    def test_exports_and_imports(self) -> None:
        pe = pefile.PE(str(DLL))
        self.assertEqual({s.name.decode() for s in pe.DIRECTORY_ENTRY_EXPORT.symbols if s.name},
                         {"VvfpStartup", "VvfpSharpPictureInstalled", "VvfpSharpPictureRect"})
        self.assertLessEqual({e.dll.decode().upper() for e in pe.DIRECTORY_ENTRY_IMPORT},
                             {"KERNEL32.DLL", "USER32.DLL", "GDI32.DLL"})
        if TEST_DLL.is_file():
            test = pefile.PE(str(TEST_DLL))
            self.assertEqual({s.name.decode() for s in test.DIRECTORY_ENTRY_EXPORT.symbols if s.name},
                             {"VvfpStartup", "VvfpSharpPictureInstalled", "VvfpSharpPictureRect",
                              "VvfpSharpPictureTestPicture", "VvfpSharpPictureTestUseModule"})

    def test_the_source(self) -> None:
        text = SOURCE.read_text(encoding="utf-8")
        for never in ("WriteProcessMemory", "VirtualAlloc", "WriteFile", "OutputDebugString", "printf",
                      "MessageBox", "SetWindowsHookEx"):
            self.assertNotIn(never, text)
        self.assertEqual(text.count("VirtualProtect("), 2)
        self.assertEqual(text.count("sp_set("), 6)   # the definition and five entries
        self.assertIn('"SDL_CreateWindow"', text)
        self.assertIn('GetModuleHandleW(L"d3d9.dll")', text)
        self.assertNotIn("LoadLibrary", text)
        self.assertNotIn("LoadLibrary", text)
        self.assertIn("D3DCREATE_FPU_PRESERVE", text)
        self.assertIn("#define SP_LATE_MS 20.0", text)
        # the shaders: one source for the build (fxc) and the research prototype's algorithm
        hlsl = (NATIVE / "sharp_picture.hlsl").read_text(encoding="utf-8")
        for entry in ("ed_step1", "ed_step2", "fit_rows", "fit_columns", "vs_quad"):
            self.assertIn(f"{entry}(", hlsl)
            self.assertIn(f'#include "sharp_picture_{entry}.h"', text)


@unittest.skipUnless(CL.is_file(), "the 32-bit MSVC toolchain is not installed")
@unittest.skipUnless(sdl2_dll() is not None, "the games' SDL2.dll (2.0.3) is not on this machine")
@unittest.skipUnless(TEST_DLL.is_file() and STOCK.is_file(), "the test build or the stock executable is not present")
class RealSdlAndDirect3D(unittest.TestCase):
    """The game's own frame routine, the games' SDL2.dll and Direct3D (a hidden window)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory(prefix="vvfp_sp_")
        out = Path(cls.tmp.name)
        cls.exe = out / "sharp_picture_harness.exe"
        build = subprocess.run(
            [str(CL), "/nologo", f"/Fo{out}\\", "/O2", "/MT", "/W4", "/D_CRT_SECURE_NO_WARNINGS",
             "/I", str(VS_TOOLS / "include"), "/I", str(SDK / "Include" / SDK_VERSION / "um"),
             "/I", str(SDK / "Include" / SDK_VERSION / "shared"), "/I", str(SDK / "Include" / SDK_VERSION / "ucrt"),
             str(HARNESS), str(FILTERS), "/link", "/BASE:0x30000000", "/DYNAMICBASE:NO",
             f"/LIBPATH:{VS_TOOLS / 'lib' / 'x86'}", f"/LIBPATH:{SDK / 'Lib' / SDK_VERSION / 'um' / 'x86'}",
             f"/LIBPATH:{SDK / 'Lib' / SDK_VERSION / 'ucrt' / 'x86'}",
             f"/OUT:{cls.exe}", "user32.lib", "gdi32.lib", "shell32.lib", "ole32.lib"],
            capture_output=True, text=True, cwd=out, timeout=600)
        if build.returncode != 0:
            raise AssertionError(build.stdout + build.stderr)
        cls.sdl = out / "sdl"
        cls.sdl.mkdir()
        shutil.copy2(sdl2_dll(), cls.sdl / "SDL2.dll")
        cls.dll = out / TEST_DLL.name
        shutil.copy2(TEST_DLL, cls.dll)
        # A New Believers frame from the game's own art in this repository (1024x768, ARGB8888 little-endian).
        from PIL import Image
        image = Image.open(ROOT / "assets" / "candidates" / "vv5_full_mastery" / "provenance" / "VV5Mockup.jpg")
        r, g, b = image.convert("RGB").split()
        cls.frame = out / "frame.argb"
        cls.frame.write_bytes(Image.merge("RGBA", (b, g, r, Image.new("L", image.size, 255))).tobytes())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def run_harness(self, *mode: str) -> str:
        args = [str(self.exe), str(self.sdl), str(STOCK), "5", str(self.dll), str(self.frame),
                str(Path(self.tmp.name) / "vv5"), *mode]
        result = subprocess.run(args, capture_output=True, text=True, timeout=600)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("\nFAIL ", "\n" + result.stdout)
        return result.stdout

    def test_bars(self) -> None:
        out = self.run_harness("fixed")
        self.assertIn("ok installed with the stock SDL 2.0.3 and game", out)
        self.assertRegex(out, r"ok the window opens at 1024x768 times the Windows scaling")
        self.assertRegex(out, r"ok window: the picture is the filter's \(largest difference [0-8]/255")
        self.assertRegex(out, r"ok screen: the picture is the filter's \(largest difference [0-8]/255")
        self.assertIn("ok window: a click on the picture reaches the game", out)

    def test_stretch(self) -> None:
        out = self.run_harness("fixed", "stretch")
        self.assertIn("ok window: the picture fills the window (stretch)", out)
        self.assertRegex(out, r"ok screen: the picture is the filter's \(largest difference [0-8]/255")

    def test_a_changed_frame_routine_installs_nothing(self) -> None:
        out = self.run_harness("refused")
        self.assertIn("ok nothing installed when the frame routine is not the stock one", out)


if __name__ == "__main__":
    unittest.main()
