"""The Tree of Life, Change Appearance: the Head and Body previews read the sheets the game draws (fixed in
v1.35.86).

THE BUG.  `appearance_draw_cell` (native/vv4_origins_icons/vv4_origins_icons.c) named the body sheet
`<sex>_bodies<age><page>.png`, the age digit 1 for a villager drawn with the old head (the head look Old,
or Auto at 55 and over).  A head sheet's first digit is the old half of the head atlas (`_heads10.png`),
but a body sheet's first digit is its place across the body atlas' 2 x 3 grid of sheets (0: columns
0-15; 1: columns 16-31) -- the body is never drawn from another sheet for an old villager.  So the
preview showed column 24 of the body atlas (another direction's frame) instead of the body.

THE PROOF.  The shipped "VVFP VV4 Origins Icons.dll" runs in Unicorn on the executable the patcher builds
with every public The Tree of Life patch: ShowOriginsAppearancePicker opens the window for a villager
(DialogBoxParamA is answered by keeping the window's procedure), then the window procedure gets the
WM_DRAWITEM of the Head and the Body previews.  Every picture the DLL opens (GdipCreateBitmapFromFile) and
the cell it copies (GdipDrawImageRectRectI) are recorded.  For both sexes, young and old ages, each head
look ("VVFP Head Look.dll" answered by stand-in exports) and bodies on each page: the head comes from
`_heads10.png` exactly when the villager is drawn old, and the body ALWAYS from `_bodies0<page>.png`, the
cell the young preview shows.

It needs Unicorn/pefile and the stock The Tree of Life (inputs/vv4-stock-copy); without them it skips.
"""
from __future__ import annotations

import functools
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

DLL = ROOT / "assets" / "origins" / "VVFP VV4 Origins Icons.dll"

try:
    import pefile  # noqa: F401
    from story_emulator import Process
    HAVE_UNICORN = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_UNICORN = False

WM_DRAWITEM = 0x2B
ID_HEAD_PIC, ID_BODY_PIC = 2003, 2013
HEAD, BODY, SEX, AGE = 0x1BB8, 0x1BBC, 0x1B90, 0x1B8C
CELL_W, CELL_H = 40, 65
HEAD_COL, BODY_COL, ROWS_PER_PAGE = 5, 8, 10
AUTO, YOUNG, OLD = 0, 1, 2
FAKE_HEAD_LOOK = 0x0C000000            # the stand-in "VVFP Head Look.dll"
HDC, HWND = 0x5D0, 0x5A0


def _stock() -> Path:
    import test_head_look as hl
    return hl.stock_path(4)


def _have() -> bool:
    try:
        return HAVE_UNICORN and DLL.is_file() and _stock().is_file()
    except Exception:  # noqa: BLE001
        return False


@functools.lru_cache(maxsize=None)
def _patched() -> bytes:
    import test_head_look as hl
    return hl.rendered(4, "immediate_fixed")


class Window:
    """The DLL in the game, with the APIs the Change Appearance window reaches answered."""

    def __init__(self, exe: bytes, look: int | None) -> None:
        self.p = p = Process(exe, DLL)
        self.look = look
        self.opened: list[str] = []
        self.cells: list[tuple[int, int, int, int]] = []
        self.proc = 0
        self._bitmaps = 0
        exports = {}
        if look is not None:
            # VvfpHeadLookInstalled(game) / Get(game, rec) / Set(game, rec, look) / SetMany(4 args).
            page = FAKE_HEAD_LOOK
            p.mu.mem_map(page, 0x1000)
            code = {"VvfpHeadLookInstalled": b"\xB8\x01\x00\x00\x00\xC2\x04\x00",
                    "VvfpHeadLookGet": b"\xB8" + struct.pack("<I", look) + b"\xC2\x08\x00",
                    "VvfpHeadLookSet": b"\xB8\x01\x00\x00\x00\xC2\x0C\x00",
                    "VvfpHeadLookSetMany": b"\xB8\x01\x00\x00\x00\xC2\x10\x00"}
            for k, (name, body) in enumerate(code.items()):
                p.write(page + 0x100 + 0x20 * k, body)
                exports[name] = page + 0x100 + 0x20 * k
        h = p.api_handlers
        h["GetModuleHandleA"] = lambda q: (
            FAKE_HEAD_LOOK if exports and q.cstring(q.arg(0)) == "VVFP Head Look.dll" else 0, 4)
        h["GetProcAddress"] = lambda q: (
            exports.get(q.cstring(q.arg(1)), 0) if q.arg(0) == FAKE_HEAD_LOOK else 0, 8)
        h["GdiplusStartup"] = self._gdiplus_startup
        h["GetForegroundWindow"] = lambda q: (HWND, 0)
        h["GetTickCount"] = lambda q: (12345, 0)
        h["DialogBoxParamA"] = self._dialog
        h["FillRect"] = lambda q: (1, 12)
        h["GdipCreateBitmapFromFile"] = self._bitmap
        h["GdipCreateFromHDC"] = self._graphics
        h["GdipDrawImageRectRectI"] = self._draw
        h["GdipDeleteGraphics"] = lambda q: (0, 4)
        h["GdipDisposeImage"] = lambda q: (0, 4)
        h["wsprintfW"] = self._wsprintf_w

    @staticmethod
    def _wsprintf_w(q):
        """wsprintfW (cdecl) for the formats the previews use: %ls and %d."""
        out, fmt = q.arg(0), q.wstring(q.arg(1))
        index, text, i = 2, "", 0
        while i < len(fmt):
            if fmt[i] != "%":
                text += fmt[i]
                i += 1
                continue
            spec = fmt[i + 1:i + 3] if fmt[i + 1:i + 3] == "ls" else fmt[i + 1]
            i += 1 + len(spec)
            value = q.arg(index)
            index += 1
            if spec == "ls":
                text += q.wstring(value)
            elif spec == "d":
                text += str(value - (1 << 32) if value & 0x80000000 else value)
            else:
                raise AssertionError(f"wsprintfW: unsupported %{spec}")
        q.write(out, text.encode("utf-16-le") + b"\0\0")
        return len(text), 0

    def _gdiplus_startup(self, q):
        q.put32(q.arg(0), 0x77)
        return 0, 12

    def _dialog(self, q):
        self.proc = q.arg(3)          # DialogBoxParamA(instance, template, owner, proc, param)
        return 0, 20

    def _bitmap(self, q):
        self.opened.append(q.wstring(q.arg(0)))
        self._bitmaps += 1
        q.put32(q.arg(1), 0x6000 + self._bitmaps)
        return 0, 8

    def _graphics(self, q):
        q.put32(q.arg(1), 0x6800)
        return 0, 8

    def _draw(self, q):
        # (graphics, image, dstx, dsty, dstw, dsth, srcx, srcy, srcw, srch, unit, attributes, callback, data)
        self.cells.append(tuple(q.arg(i) for i in (6, 7, 8, 9)))
        return 0, 56

    def open(self, *, sex: int, age: int, head: int, body: int) -> None:
        p = self.p
        rec = self.rec = p.alloc(0x2E3C)
        p.put32(rec + SEX, sex)
        p.put32(rec + AGE, age)
        p.put32(rec + HEAD, head)
        p.put32(rec + BODY, body)
        p.export("ShowOriginsAppearancePicker", rec)
        assert self.proc, "the window was not opened"

    def draw(self, control: int) -> tuple[str, tuple[int, int, int, int]]:
        p = self.p
        dis = p.alloc(0x40)
        # DRAWITEMSTRUCT: CtlType, CtlID, itemID, itemAction, itemState, hwndItem, hDC, rcItem{l,t,r,b}
        p.write(dis, struct.pack("<IIIIIIIiiii", 4, control, 0, 1, 0, 0x5B0, HDC, 0, 0, 80, 130))
        self.opened.clear()
        self.cells.clear()
        assert p.call(self.proc, [HWND, WM_DRAWITEM, control, dis]) == 1
        assert len(self.opened) == 1 and len(self.cells) == 1, (self.opened, self.cells)
        return self.opened[0], self.cells[0]


@unittest.skipUnless(_have(), "Unicorn/pefile, the stock The Tree of Life or the companion DLL is missing")
class PreviewsReadTheGamesSheets(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            cls.exe = _patched()
        except Exception as exc:  # noqa: BLE001 -- the patcher could not build it here
            raise unittest.SkipTest(f"the patched executable could not be built ({exc})")

    def test_head_and_body_for_every_look_age_and_page(self) -> None:
        n = 0
        for look in (None, AUTO, YOUNG, OLD):           # None: the Head Look DLL is not in the game
            for sex, word in ((0, "male"), (1, "female")):
                for age in (300, 1099, 1100, 2400):
                    old = look == OLD or (look in (None, AUTO) and age >= 1100)
                    for head, body in ((0, 0), (7, 9), (12, 10), (29, 23), (3, 28)):
                        with self.subTest(look=look, sex=word, age=age, head=head, body=body):
                            w = Window(self.exe, look)
                            w.open(sex=sex, age=age, head=head, body=body)
                            file, cell = w.draw(ID_HEAD_PIC)
                            self.assertEqual(file, f"Images\\{word}_heads{1 if old else 0}0.png")
                            self.assertEqual(cell, (HEAD_COL * CELL_W, head * CELL_H, CELL_W, CELL_H))
                            file, cell = w.draw(ID_BODY_PIC)
                            self.assertEqual(file, f"Images\\{word}_bodies0{body // ROWS_PER_PAGE}.png")
                            self.assertEqual(cell, (BODY_COL * CELL_W, (body % ROWS_PER_PAGE) * CELL_H,
                                                    CELL_W, CELL_H))
                            n += 1
        self.assertEqual(n, 4 * 2 * 4 * 5)


class TheSourceNamesTheBodySheetWithoutTheAge(unittest.TestCase):
    """Runs everywhere (CI has no executables): the body sheet's first digit is 0, never the look's."""

    def test_the_format(self) -> None:
        source = (ROOT / "native" / "vv4_origins_icons" / "vv4_origins_icons.c").read_text(encoding="utf-8")
        body = source[source.index("static void appearance_draw_cell("):]
        body = body[:body.index("\n}\n")]
        self.assertIn('L"Images\\\\%ls_bodies0%d.png", sex, page', body)
        self.assertNotIn("_bodies%d%d", body)


if __name__ == "__main__":
    unittest.main()
