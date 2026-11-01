"""The emulated game for tests/test_translations_runtime.py: a stock executable with "VVFP Translations.dll"
mapped beside it (tests/story_emulator.py), a game folder holding the patcher's Translation.txt, and the few
kernel32 / user32 answers the DLL asks for.  VvfpStartup is called directly, as "VVFP Startup.dll" would."""
from __future__ import annotations

import glob
import struct
from pathlib import Path

from story_emulator import Process

ROOT = Path(__file__).resolve().parents[1]
DLL = ROOT / "assets" / "translations" / "VVFP Translations.dll"
EXE_PATH = "C:\\Games\\Village\\Game.exe"
TRANSLATION = "C:\\Games\\Village\\Virtual Villagers Fun Patcher Files\\Translation\\Translation.txt"
INVALID = 0xFFFFFFFF
GLYPHS_MODULE = 0x0C000000

TITLES = {
    1: "Virtual Villagers - A New Home",
    2: "Virtual Villagers - The Lost Children",
    3: "Virtual Villagers - The Secret City",
    4: "Virtual Villagers - The Tree of Life",
    5: "Virtual Villagers - New Believers",
}


def stock_exe(game: int) -> Path | None:
    found = glob.glob(str(ROOT / "inputs" / f"vv{game}-stock-copy" / "*.exe"))
    return Path(found[0]) if found else None


class Game:
    """One game process with the DLL; `files` maps a full path to its bytes."""

    def __init__(self, game: int, exe: bytes, translation: bytes | None, *, glyphs: int | None = None,
                 glyphs_dll: str = "VVFP Unicode Text.dll", font_shipped: bool = False):
        self.game = game
        self.p = p = Process(exe, DLL)
        p.exe_path = EXE_PATH.encode()
        self.files = {}
        if translation is not None:
            self.files[TRANSLATION.lower()] = translation
        self.handles: dict[int, list] = {}
        self.writes: list[tuple[int, int]] = []
        self.hooks: list[tuple] = []
        self.glyphs = glyphs
        # Which companion answers: "VVFP Unicode Text.dll" (started before Translations), or "VVFP Unicode
        # Font.dll" -- already loaded, or (font_shipped) only shipped beside it, loaded and started on use.
        self.glyphs_dll = glyphs_dll
        self.font_shipped = font_shipped
        self.font_loaded = False
        self.font_started: list[tuple[int, int]] = []
        if glyphs is not None:
            # A fake module exporting VvfpGlyphsUtf8 (`mov eax, glyphs; ret`) and VvfpStartup (`ret 8`).
            p.mu.mem_map(GLYPHS_MODULE, 0x1000)
            p.write(GLYPHS_MODULE, b"\xB8" + struct.pack("<I", glyphs) + b"\xC3")
            p.write(GLYPHS_MODULE + 0x10, b"\xC2\x08\x00")
        h = p.api_handlers
        h.update(
            CreateFileW=self._open, GetFileSizeEx=self._size, ReadFile=self._read, CloseHandle=self._close,
            VirtualAlloc=self._valloc, VirtualFree=lambda p: (1, 12), GetModuleHandleW=self._module,
            GetProcAddress=self._proc, GetCurrentThreadId=lambda p: (0x1234, 0),
            SetWindowsHookExW=self._hook, GetFileAttributesW=self._attributes, LoadLibraryExW=self._load,
        )

    # -- the APIs -----------------------------------------------------------------------------------
    def _open(self, p):
        path = p.wstring(p.arg(0)).lower()
        if path not in self.files:
            return INVALID, 28
        handle = 0x500 + 4 * len(self.handles)
        self.handles[handle] = [path, 0]
        return handle, 28

    def _size(self, p):
        path, _ = self.handles[p.arg(0)]
        p.write(p.arg(1), struct.pack("<Q", len(self.files[path])))
        return 1, 8

    def _read(self, p):
        path, at = self.handles[p.arg(0)]
        data = self.files[path][at:at + p.arg(2)]
        self.handles[p.arg(0)][1] += len(data)
        p.write(p.arg(1), data)
        if p.arg(3):
            p.put32(p.arg(3), len(data))
        return 1, 20

    def _close(self, p):
        self.handles.pop(p.arg(0), None)
        return 1, 4

    def _valloc(self, p):
        return p.alloc(p.arg(1)), 16

    def _module(self, p):
        name = p.wstring(p.arg(0))
        if self.glyphs is not None and name == self.glyphs_dll and (not self.font_shipped or self.font_loaded):
            return GLYPHS_MODULE, 4
        return 0, 4

    FONT_PATH = "C:\\Games\\Village\\Virtual Villagers Fun Patcher Files\\VVFP Unicode Font.dll"

    def _attributes(self, p):
        if self.font_shipped and p.wstring(p.arg(0)).lower() == self.FONT_PATH.lower():
            return 0x20, 4
        return INVALID, 4

    def _load(self, p):
        if self.font_shipped and self.glyphs is not None and p.wstring(p.arg(0)).lower() == self.FONT_PATH.lower():
            self.font_loaded = True
            return GLYPHS_MODULE, 12
        return 0, 12

    def _proc(self, p):
        name = p.cstring(p.arg(1))
        if p.arg(0) == GLYPHS_MODULE and name == "VvfpGlyphsUtf8":
            return GLYPHS_MODULE, 8
        if p.arg(0) == GLYPHS_MODULE and name == "VvfpStartup":
            self.font_started.append((self.game, 0))
            return GLYPHS_MODULE + 0x10, 8
        return 0, 8

    def _hook(self, p):
        self.hooks.append((p.arg(0), p.arg(1), p.arg(3)))
        return 0x77, 16

    # -- running ------------------------------------------------------------------------------------
    def start(self) -> None:
        self.p.export("VvfpStartup", self.game, 0)

    def active(self) -> int:
        return self.p.export("VvfpTranslationsActive")

    def translate(self, text: bytes) -> bytes:
        at = self.p.alloc(len(text) + 1)
        self.p.write(at, text + b"\0")
        out = self.p.export("VvfpTranslateText", at)
        return self.raw(out)

    def raw(self, va: int, limit: int = 8192) -> bytes:
        out = bytearray()
        while len(out) < limit:
            b = self.p.read(va + len(out), 1)
            if b == b"\0":
                break
            out += b
        return bytes(out)
