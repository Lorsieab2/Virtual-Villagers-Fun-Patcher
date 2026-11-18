"""The Village Solidarity Tech screen counter of The Secret City, The Tree of Life and New Believers
(native/vvfp_village_solidarity/counter_vv3.inc, counter_vv4.inc, counter_vv5.inc), run in the unicorn PE
emulator over each stock executable with the TEST build of the companion:

* VvfpStartup splices exactly the Tech screen draw's epilogue (a jmp and nops) and nothing else there;
* running the spliced epilogue draws the counter once through the game's own draw wrapper, with the UI font of the
  resource singleton, the expected colour, inside the counter's strip, and returns with the stack exactly as the
  stock epilogue leaves it;
* a text too wide for the strip is wrapped onto a second line and cut with "...", never past the strip;
* a build whose epilogue is not stock is never spliced.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

try:
    from story_emulator import RETURN, STACK_TOP, Process

    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

DLL = ROOT / "tests" / "test_dlls" / "VVFP Village Solidarity.test.dll"
EXES = {3: "Virtual Villagers - The Secret City.exe", 4: "Virtual Villagers - The Tree of Life.exe",
        5: "Virtual Villagers - New Believers.exe"}
STOCK = {g: ROOT / "research" / "stock-executables" / name for g, name in EXES.items()}

# site, its stock bytes, registers the epilogue pops, its `add esp`, renderer getter, resource getter, draw wrapper,
# width, line height, colour (an immediate or a global's address), strip (left, right, y)
GAMES = {
    3: (0x464C1D, "5f5e83c424c3", 2, 0x24, 0x408940, 0x42F740, 0x40A060, 0x402230, 0x4021C0,
        ("value", 0xFF002245), (500, 735, 8)),
    4: (0x43E87E, "5f5e5d5b83c418c3", 4, 0x18, 0x408130, 0x44DA20, 0x409BD0, 0x402430, 0x402500,
        ("global", 0x4BEEC4), (30, 270, 8)),
    5: (0x44121C, "5e5d5b83c428c3", 3, 0x28, 0x4080C0, 0x450D40, 0x409EA0, 0x4023E0, 0x4024B0,
        ("global", 0x4CD284), (45, 370, 8)),
}

pytestmark = pytest.mark.skipif(
    not HAVE_EMULATOR or not DLL.is_file() or not all(p.is_file() for p in STOCK.values()),
    reason="needs the emulator, the TEST companion and the stock executables")

if HAVE_EMULATOR:
    class _Process(Process):
        """The few Windows calls the companion's score file makes, answered as on a machine with no file yet."""

        def _api_EnterCriticalSection(self):
            return 0, 4

        def _api_LeaveCriticalSection(self):
            return 0, 4

        def _api_GetLocalTime(self):
            return 0, 4

        def _api_CreateDirectoryW(self):
            return 0, 8

        def _api_CreateFileA(self):
            return 0xFFFFFFFF, 28

        def _api_wsprintfW(self):                          # the log's path: none, so no log is written
            self.write(self.arg(0), b"\0\0")
            return 0, 0

        def _api_GetModuleHandleW(self):
            return 0, 4

        def _api_SHGetSpecialFolderPathW(self):
            self.write(self.arg(1), "C:\\Docs".encode("utf-16-le") + b"\0\0")
            return 1, 16

        def _api_WideCharToMultiByte(self):
            src, text = self.arg(2), b""
            while self.read(src + len(text), 2) != b"\0\0":
                text += self.read(src + len(text), 2)
            out = text.decode("utf-16-le").encode("latin1", "replace") + b"\0"
            if self.arg(4):
                self.write(self.arg(4), out)
            if self.arg(7):
                self.put32(self.arg(7), 0)
            return len(out), 32


def _cstring(p, va: int) -> bytes:
    out = b""
    while (c := p.read(va + len(out), 1)) != b"\0":
        out += c
    return out


def _draw(game: int, char_width: int, *, exe: bytes | None = None):
    site, stock, pops, add, renderer, resources, draw, width, height, colour, strip = GAMES[game]
    p = _Process(exe if exe is not None else STOCK[game].read_bytes(), DLL)
    p.export("VvfpStartup", game, 0)
    installed = p.export("VvfpVillageScoreCounterInstalled", game)
    spliced = p.read(site, len(bytes.fromhex(stock)))
    p.export("VvfpVillageScoreProbeStart", game, 1, 10)
    font, holder, wrapper = p.alloc(16), p.alloc(16), p.alloc(16)
    p.put32(holder, font)
    if colour[0] == "global":
        p.put32(colour[1], 0xFFEEDDCC)
    calls = []
    p.stub(renderer, lambda q: (wrapper, 0))
    p.stub(resources, lambda q: (holder, 0))
    p.stub(width, lambda q: (len(_cstring(q, q.arg(0))) * char_width, 8))
    p.stub(height, lambda q: (18, 4))

    def on_draw(q):
        calls.append((_cstring(q, q.arg(0)).decode("latin1"), q.arg(1), q.arg(2), q.arg(3), q.arg(4), q.reg("ecx")))
        return 0, 0x14

    p.stub(draw, on_draw)
    esp = STACK_TOP - 0x1000
    esp -= 4
    p.put32(esp, RETURN)
    esp -= add
    for i in range(pops):
        esp -= 4
        p.put32(esp, 0x1111 * (i + 1))
    p.set_reg("esp", esp)
    if installed:
        p.run(site, RETURN)
    return installed, spliced, calls, p.reg("esp"), (font, wrapper)


@pytest.mark.parametrize("game", (3, 4, 5))
def test_the_epilogue_is_spliced_and_draws_the_counter_once(game):
    site, stock, *_rest, colour, strip = GAMES[game]
    installed, spliced, calls, esp, (font, wrapper) = _draw(game, 7)
    assert installed == 1
    assert spliced[0] == 0xE9 and spliced[5:] == b"\x90" * (len(spliced) - 5)
    assert esp == STACK_TOP - 0x1000                       # the stock epilogue's stack, after its ret
    assert len(calls) == 1
    text, x, y, argb, drawn_font, drawn_wrapper = calls[0]
    assert text == "Village Solidarity: 50 / 100"
    assert (drawn_font, drawn_wrapper) == (font, wrapper)
    assert argb == (colour[1] if colour[0] == "value" else 0xFFEEDDCC)
    left, right, top = strip
    assert y == top and left <= x and x + len(text) * 7 <= right
    assert x - left == (right - left - len(text) * 7) // 2  # centred in the strip


@pytest.mark.parametrize("game", (3, 4, 5))
def test_too_wide_wraps_and_cuts_inside_the_strip(game):
    *_rest, strip = GAMES[game]
    left, right, top = strip
    char_width = (right - left) // 14 + 1                  # "Village Solidarity: 50 / 100" is twice too wide
    installed, _spliced, calls, esp, _ = _draw(game, char_width)
    assert installed == 1 and esp == STACK_TOP - 0x1000
    assert 1 <= len(calls) <= 2
    for text, x, _y, *_ in calls:
        assert left <= x and x + len(text.encode("latin1")) * char_width <= right
    assert calls[0][2] == top
    if len(calls) == 2:
        assert calls[1][2] == top + 18
    shown = " ".join(c[0] for c in calls)
    assert shown.startswith("Village") and (shown.endswith("...") or shown.endswith("100"))


@pytest.mark.parametrize("game", (3, 4, 5))
def test_a_build_whose_epilogue_is_not_stock_is_never_spliced(game):
    site, stock, *_rest = GAMES[game]
    data = bytearray(STOCK[game].read_bytes())
    import pefile

    pe = pefile.PE(data=bytes(data), fast_load=True)
    offset = pe.get_offset_from_rva(site - pe.OPTIONAL_HEADER.ImageBase)
    assert data[offset:offset + len(bytes.fromhex(stock))] == bytes.fromhex(stock)
    data[offset] = 0x90
    installed, spliced, calls, _esp, _ = _draw(game, 7, exe=bytes(data))
    assert installed == 0 and calls == []
    assert spliced[0] == 0x90 and spliced[1:] == bytes.fromhex(stock)[1:]
