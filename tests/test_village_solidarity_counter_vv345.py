"""The Village Solidarity Tech screen counter and its "?" button of The Secret City, The Tree of Life and New
Believers (native/vvfp_village_solidarity/counter_vv3.inc, counter_vv4.inc, counter_vv5.inc), run in the unicorn PE
emulator over each stock executable with the TEST build of the companion:

* VvfpStartup writes exactly three sites -- the Tech screen draw's epilogue, a point in its constructor (each a jmp
  and nops) and the screen's vtable slot 3 -- and nothing else;
* the spliced epilogue draws the counter once through the game's own draw wrapper, in the Tech screen's OWN font
  (the draw context's current font, [ctx+0x5C], the one its title is drawn in: the owner, 2026-11-18), the screen's
  colour, inside the counter's strip left of the "?", and returns with the stack exactly as the stock epilogue does;
* the constructor point makes the "?" button as the screen makes its technologies' own (the same picture id, the
  same constructor, the "?" label in the same three colours, attached to the screen), then runs the replaced
  instruction and goes on in the stock constructor;
* slot 3 shows the owner's help -- title and words -- in the technologies' own message box (its sound first, then
  the box's constructor, its modal loop with the screen as parent, its destructor), for the "?" only; any other
  message goes on to the stock handler;
* a build whose sites are not stock is never written.
"""

from __future__ import annotations

import struct
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
BUTTON_ID = 0x534F
OWNERS_HELP = ("Village Solidarity shows how close and united your village feels, from 0 to 100. Good Island event "
               "outcomes raise it, bad ones lower it. High Solidarity (greater than 50) can increase the likelihood "
               "of more good events happening, while Low Solidarity (less than 50) does the opposite.")

# The draw: site, its stock bytes, registers its epilogue pops, its `add esp`, renderer getter, resource getter,
# draw wrapper, width, line height, colour (an immediate or a global's address), strip (left, right, middle y),
# the "?" picture's size.
GAMES = {
    3: (0x464C1D, "5f5e83c424c3", 2, 0x24, 0x408940, 0x42F740, 0x40A060, 0x402230, 0x4021C0,
        ("value", 0xFF002245), (500, 735, 20), (37, 28)),
    4: (0x43E87E, "5f5e5d5b83c418c3", 4, 0x18, 0x408130, 0x44DA20, 0x409BD0, 0x402430, 0x402500,
        ("global", 0x4BEEC4), (535, 785, 20), (37, 40)),
    5: (0x44121C, "5e5d5b83c428c3", 3, 0x28, 0x4080C0, 0x450D40, 0x409EA0, 0x4023E0, 0x4024B0,
        ("global", 0x4CD284), (645, 990, 20), (37, 40)),
}
# The button and the help: the constructor point, its stock bytes, where it goes on; operator new, the image manager,
# its lookup, the picture id, the button constructor, its label, the label colours' first global, the "?" string,
# The Tree of Life's extra call, attach; the box's constructor, modal loop, destructor; the sound, its player, its id;
# the slot and the stock handler.
BUTTONS = {
    3: (0x4652A8, "c744241001000000", 0x4652B0, 0x46EC93, 0x42E9D0, 0x42E8A0, 0x5A, 0x4019F0, 0x401620, 0x4B1FF8,
        0x47F288, 0, 0x40C1F0, 0x41C7A0, 0x401AF0, 0x41C2F0, 0x424110, 0x581A38, 0x64, 0x49E840, 0x465640),
    4: (0x43E16B, "64890d00000000", 0x43E172, 0x470C5C, 0x44CCF0, 0x44CB70, 0xEB, 0x401C20, 0x401600, 0x4BEEE0,
        0x48CCC4, 0x401630, 0x40C190, 0x419F00, 0x401D40, 0x419D50, 0x448E10, 0x4DA020, 0x64, 0x48EC70, 0x43E9F0),
    5: (0x4407B7, "c744241401000000", 0x4407BF, 0x47BBDC, 0x44FBB0, 0x44FA30, 0xCD, 0x401BD0, 0x4015D0, 0x4CD2A0,
        0x497E94, 0, 0x40C680, 0x41A760, 0x401CF0, 0x41A5F0, 0x44C440, 0x51F440, 0x66, 0x49A218, 0x4415F0),
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

        def _api_GetModuleHandleA(self):                   # no SDL2, no Scrolling Popups, no Translations here
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


def _started(game: int, exe: bytes | None = None):
    p = _Process(exe if exe is not None else STOCK[game].read_bytes(), DLL)
    p.export("VvfpStartup", game, 0)
    return p, p.export("VvfpVillageScoreCounterInstalled", game)


def _fonts(p):
    """The title font (the draw context's current font, with glyphs) and the UI font (the resource singleton's)."""
    title, ui = p.alloc(16), p.alloc(16)
    p.put32(title + 4, p.alloc(16))
    p.put32(ui + 4, p.alloc(16))
    ctx, wrapper, holder = p.alloc(0x100), p.alloc(16), p.alloc(16)
    p.put32(ctx + 0x5C, title)
    p.put32(wrapper, ctx)
    p.put32(holder, ui)
    return title, ui, wrapper, holder


def _draw(game: int, char_width: int):
    site, stock, pops, add, renderer, resources, draw, width, height, colour, strip, _size = GAMES[game]
    p, installed = _started(game)
    spliced = p.read(site, len(bytes.fromhex(stock)))
    p.export("VvfpVillageScoreProbeStart", game, 1, 10)
    title, ui, wrapper, holder = _fonts(p)
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
    return installed, spliced, calls, p.reg("esp"), (title, wrapper)


@pytest.mark.parametrize("game", (3, 4, 5))
def test_three_sites_are_written(game):
    site, stock, *_rest = GAMES[game]
    make, make_stock, *_b = BUTTONS[game]
    slot, handler = BUTTONS[game][-2:]
    p, installed = _started(game)
    assert installed == 1
    for va, hexs in ((site, stock), (make, make_stock)):
        got = p.read(va, len(bytes.fromhex(hexs)))
        assert got[0] == 0xE9 and got[5:] == b"\x90" * (len(got) - 5)
    assert struct.unpack("<I", p.read(slot, 4))[0] != handler          # the slot points into the companion


@pytest.mark.parametrize("game", (3, 4, 5))
def test_the_counter_is_drawn_in_the_title_font_left_of_the_question_mark(game):
    *_rest, colour, strip, (bw, bh) = GAMES[game]
    installed, _spliced, calls, esp, (title, wrapper) = _draw(game, 6)
    assert installed == 1
    assert esp == STACK_TOP - 0x1000                       # the stock epilogue's stack, after its ret
    assert len(calls) == 1
    text, x, y, argb, drawn_font, drawn_wrapper = calls[0]
    assert text == "Village Solidarity: 50 / 100"
    assert (drawn_font, drawn_wrapper) == (title, wrapper)  # the Tech screen's own (title's) font
    assert argb == (colour[1] if colour[0] == "value" else 0xFFEEDDCC)
    left, right, middle = strip
    room = right - bw - 6 - left
    assert left <= x and x + len(text) * 6 <= left + room      # never under the "?"
    assert x - left == (room - len(text) * 6) // 2              # centred in the room left of it
    assert y == middle - 9                                      # centred on the strip's middle (line height 18)


@pytest.mark.parametrize("game", (3, 4, 5))
def test_too_wide_never_runs_past_its_room(game):
    *_rest, strip, (bw, _bh) = GAMES[game]
    left, right, _middle = strip
    room = right - bw - 6 - left
    installed, _spliced, calls, esp, _ = _draw(game, (right - left) // 10)
    assert installed == 1 and esp == STACK_TOP - 0x1000
    assert len(calls) == 1
    text, x, *_ = calls[0]
    assert left <= x <= left + room


@pytest.mark.parametrize("game", (3, 4, 5))
def test_the_question_mark_button_is_made_as_the_technologies_own(game):
    (make, _stock, resume, op_new, images_get, image_get, image_id, button_new, label, colours, qmark, extra,
     add_child, *_rest) = BUTTONS[game]
    *_draw_rest, strip, (bw, bh) = GAMES[game]
    p, installed = _started(game)
    assert installed == 1
    screen, button, manager, picture = p.alloc(0x200), p.alloc(0x40), p.alloc(16), p.alloc(16)
    for k in range(3):
        p.put32(colours + 4 * k, 0xFF000000 + k)
    seen = {}
    p.stub(op_new, lambda q: (seen.setdefault("new", q.arg(0)) and button, 0))
    p.stub(images_get, lambda q: (manager, 0))
    p.stub(image_get, lambda q: (seen.setdefault("image", (q.reg("ecx"), q.arg(0))) and picture, 4))

    def make_button(q):
        seen["button"] = (q.reg("ecx"), q.arg(0), q.arg(1), q.arg(2), q.arg(3), q.arg(4), q.arg(5))
        return q.reg("ecx"), 0x18
    p.stub(button_new, make_button)
    p.stub(label, lambda q: (seen.setdefault("label", (q.reg("ecx"), _cstring(q, q.arg(0)), q.arg(1), q.arg(2),
                                                         q.arg(3), q.arg(4))) and 0, 0x14))
    if extra:
        p.stub(extra, lambda q: (seen.setdefault("extra", (q.arg(0), q.arg(1))) and 0, 8))
    p.stub(add_child, lambda q: (seen.setdefault("child", (q.reg("ecx"), q.arg(0))) and 0, 4))
    esp = STACK_TOP - 0x1000
    p.set_reg("esp", esp)
    p.set_reg("esi", screen)
    p.run(make, resume)
    left, right, middle = strip
    assert seen["new"] == 0x14
    assert seen["image"] == (manager, image_id)
    assert seen["button"] == (button, BUTTON_ID, picture, right - bw, middle - bh // 2, screen, 0)
    assert seen["label"] == (button, b"?", 0xFF000000, 0xFF000001, 0xFF000002, 0)
    if extra:
        assert seen["extra"] == (3, 1)
    assert seen["child"] == (screen, button)
    assert p.reg("esp") == esp                              # the constructor's own stack, untouched


@pytest.mark.parametrize("game", (3, 4, 5))
def test_the_question_mark_shows_the_owners_help_in_the_games_message_box(game):
    resources, width = GAMES[game][5], GAMES[game][7]
    (*_b, box_new, box_run, box_free, sound, sounds, sound_id, slot, handler) = BUTTONS[game]
    p, installed = _started(game)
    assert installed == 1
    _title, _ui, _wrapper, holder = _fonts(p)
    p.stub(resources, lambda q: (holder, 0))
    p.stub(width, lambda q: (len(_cstring(q, q.arg(0))) * 8, 8))
    order = []
    p.stub(sound, lambda q: (order.append(("sound", q.reg("ecx"), q.arg(0))) or 0, 4))
    p.stub(box_new, lambda q: (order.append(("box", _cstring(q, q.arg(0)).decode("latin1"), q.arg(1), q.arg(2)))
                               or q.reg("ecx"), 0xC))
    p.stub(box_run, lambda q: (order.append(("run", q.arg(0), q.arg(1))) or 0, 8))
    p.stub(box_free, lambda q: (order.append(("free",)) or 0, 0))
    p.stub(handler, lambda q: (order.append(("stock", q.arg(0), q.arg(1))) or 1, 8))
    screen = p.alloc(0x200)
    target = struct.unpack("<I", p.read(slot, 4))[0]
    for message in ((8, BUTTON_ID), (8, 3), (2, BUTTON_ID)):
        order.clear()
        esp = STACK_TOP - 0x1000
        esp -= 4
        p.put32(esp, message[1])
        esp -= 4
        p.put32(esp, message[0])
        esp -= 4
        p.put32(esp, RETURN)
        p.set_reg("esp", esp)
        p.set_reg("ecx", screen)
        p.run(target, RETURN)
        assert p.reg("esp") == esp + 12                    # ret 8, as the stock handler
        if message == (8, BUTTON_ID):
            assert [o[0] for o in order] == ["sound", "box", "run", "free"]
            assert order[0][1:] == (sounds, sound_id)
            text = order[1][1]
            assert text.startswith("Village Solidarity\n\n")
            assert " ".join(text.split("\n\n", 1)[1].split("\n")) == OWNERS_HELP
            assert order[2][1:] == (screen, 0)
        else:
            assert order == [("stock", message[0], message[1])]


@pytest.mark.parametrize("game", (3, 4, 5))
def test_a_build_whose_epilogue_is_not_stock_is_never_spliced(game):
    site, stock, *_rest = GAMES[game]
    make, make_stock, *_b = BUTTONS[game]
    slot, handler = BUTTONS[game][-2:]
    data = bytearray(STOCK[game].read_bytes())
    import pefile

    pe = pefile.PE(data=bytes(data), fast_load=True)
    offset = pe.get_offset_from_rva(site - pe.OPTIONAL_HEADER.ImageBase)
    assert data[offset:offset + len(bytes.fromhex(stock))] == bytes.fromhex(stock)
    data[offset] = 0x90
    p, installed = _started(game, bytes(data))
    assert installed == 0
    assert p.read(make, len(bytes.fromhex(make_stock))) == bytes.fromhex(make_stock)   # all or none
    assert struct.unpack("<I", p.read(slot, 4))[0] == handler
