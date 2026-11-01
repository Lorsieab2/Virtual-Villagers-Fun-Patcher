"""Run a published build's text box keys in unicorn, with "VVFP Copy and Paste.dll" installed.

The build is started as the game starts it (tests/startup_emulation.py: the stub, VVFP Startup.dll, every
shipped companion's VvfpStartup), then:

  * a text box is built as the game builds one (the box class's own vtable, so its own keyboard handler
    runs), registered in the game's own event manager as a keyboard listener;
  * an SDL_KEYDOWN event is laid on the pump's stack and the pump is run from its SDL_KEYDOWN case (the
    detoured site) until it either goes on with the next event (the key was handled) or reaches the stock
    case's next instruction (the key went on to the game);
  * the Windows clipboard is answered here (a Python string, or busy), and NormalizeString by Python's NFC.

Everything between -- the companion's hook, its clipboard calls, the box's own handler with its filter and
limit, the handler's change notice through the game's event manager -- runs as machine code.
"""
from __future__ import annotations

import struct
import sys
import unicodedata
from pathlib import Path

from unicorn import UC_HOOK_CODE
from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDI,
                               UC_X86_REG_EFLAGS, UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import startup_emulation as se  # noqa: E402

ARENA = 0x34000000
ARENA_SIZE = 0x00400000
CF_UNICODETEXT = 13

# Each game: the SDL_KEYDOWN site, the keysym's stack offset there, where the pump goes on, the event
# manager's global, the text box's keyboard handler and the box class's vtable.
GAMES = {
    "vv1": (0x4039D6, 0x3C, 0x403C73, 0x48AEC8, 0x40BE30, 0x4575B8),
    "vv2": (0x403C66, 0x3C, 0x403F03, 0x4997A8, 0x40C810, 0x4745EC),
    "vv3": (0x404286, 0x3C, 0x404523, 0x4B3088, 0x40D4A0, 0x47C7B0),
    "vv4": (0x4048A6, 0x38, 0x404B07, 0x4CB508, 0x40D750, 0x48A990),
    "vv5": (0x404836, 0x38, 0x404A97, 0x4DACCC, 0x40DC40, 0x4959A8),
}
SDLK_INSERT = 0x40000049
KMOD_LCTRL, KMOD_LSHIFT, KMOD_LALT, KMOD_RALT = 0x0040, 0x0001, 0x0100, 0x0200


class Clipboard:
    def __init__(self) -> None:
        self.text: str | None = None
        self.busy = False
        self.open = False
        self.opens = 0
        self.closes = 0
        self.handles: dict[int, tuple[int, int]] = {}


RUNS: dict = {}          # each machine's run: the imports answer the machine that calls them


def _register() -> None:
    current: dict = {}

    def m():
        return current["run"]

    def bind(handler):
        def call(mc, arg, ret):
            current["run"] = RUNS[id(mc)]
            handler(mc, arg, ret)
        return call

    def alloc(n: int) -> int:
        run = m()
        at = run.next
        run.next = (run.next + max(n, 1) + 15) & ~15
        assert run.next < ARENA + ARENA_SIZE
        run.mu.mem_write(at, b"\0" * max(n, 1))
        return at

    def available(mc, arg, ret):
        c = m().clip
        ret(1 if arg(0) == CF_UNICODETEXT and c.text is not None else 0)

    def open_(mc, arg, ret):
        c = m().clip
        if c.busy or c.open:
            ret(0)
            return
        c.open = True
        c.opens += 1
        ret(1)

    def close(mc, arg, ret):
        c = m().clip
        assert c.open, "CloseClipboard without OpenClipboard"
        c.open = False
        c.closes += 1
        ret(1)

    def get_data(mc, arg, ret):
        c = m().clip
        assert c.open
        if arg(0) != CF_UNICODETEXT or c.text is None:
            ret(0)
            return
        raw = c.text.encode("utf-16-le", "surrogatepass") + b"\0\0"
        at = alloc(len(raw))
        m().mu.mem_write(at, raw)
        c.handles[at] = (at, len(raw))
        ret(at)

    def global_alloc(mc, arg, ret):
        at = alloc(arg(1))
        m().clip.handles[at] = (at, arg(1))
        ret(at)

    def global_lock(mc, arg, ret):
        ret(m().clip.handles[arg(0)][0])

    def global_size(mc, arg, ret):
        ret(m().clip.handles[arg(0)][1])

    def global_free(mc, arg, ret):
        m().clip.handles.pop(arg(0), None)
        m().freed += 1
        ret(0)

    def empty(mc, arg, ret):
        c = m().clip
        assert c.open
        c.text = None
        ret(1)

    def set_data(mc, arg, ret):
        c = m().clip
        assert c.open and arg(0) == CF_UNICODETEXT
        at, size = c.handles[arg(1)]
        raw = bytes(m().mu.mem_read(at, size))
        end = next(i for i in range(0, len(raw), 2) if raw[i:i + 2] == b"\0\0")
        c.text = raw[:end].decode("utf-16-le", "surrogatepass")
        ret(arg(1))

    def normalize(mc, arg, ret):
        form, src, n, dst, room = (arg(i) for i in range(5))
        assert form == 1                                   # NormalizationC
        text = bytes(m().mu.mem_read(src, 2 * n)).decode("utf-16-le", "surrogatepass")
        try:
            out = unicodedata.normalize("NFC", text).encode("utf-16-le")
        except UnicodeEncodeError:                         # a lone surrogate: Windows fails too
            ret(0)
            return
        if len(out) // 2 > room:
            ret(0)
            return
        m().mu.mem_write(dst, out)
        ret(len(out) // 2)

    table = {
        "IsClipboardFormatAvailable": (4, available),
        "OpenClipboard": (4, open_),
        "CloseClipboard": (0, close),
        "GetClipboardData": (4, get_data),
        "EmptyClipboard": (0, empty),
        "SetClipboardData": (8, set_data),
        "GetActiveWindow": (0, lambda mc, arg, ret: ret(0x00012345)),
        "GlobalAlloc": (8, global_alloc),
        "GlobalLock": (4, global_lock),
        "GlobalUnlock": (4, lambda mc, arg, ret: ret(1)),
        "GlobalSize": (4, global_size),
        "GlobalFree": (4, global_free),
        "NormalizeString": (20, normalize),
    }
    se.EXTRA_IMPORTS.update({name: (popped, bind(handler)) for name, (popped, handler) in table.items()})


class PasteRun:
    """One published build after WinMain is reached, with a text box on a screen."""

    def __init__(self, game: str, selection, mode: str = "collection_progression") -> None:
        from test_startup_loader import run
        _register()
        self.machine, _result, self.features, _before, self.shipped = run(game, mode, tuple(selection))
        RUNS[id(self.machine)] = self
        self.game = game
        self.mu = self.machine.mu
        self.mu.mem_map(ARENA, ARENA_SIZE)
        self.next = ARENA + 0x1000
        self.freed = 0
        self.clip = Clipboard()
        self.site, self.sym, self.cont, self.manager, self.handler, self.vtable = GAMES[game]
        # the game's event manager: [global] -> manager -> list -> nodes
        self.list = self.alloc(0x10)
        manager = self.alloc(4)
        self.mu.mem_write(manager, struct.pack("<I", self.list))
        self.mu.mem_write(self.manager, struct.pack("<I", manager))

    def alloc(self, n: int) -> int:
        at = self.next
        self.next = (self.next + max(n, 1) + 15) & ~15
        self.mu.mem_write(at, b"\0" * max(n, 1))
        return at

    def dword(self, va: int) -> int:
        return struct.unpack("<I", self.mu.mem_read(va, 4))[0]

    # -- the box -----------------------------------------------------------------------------------
    def box(self, text: bytes = b"", limit: int = 27, digits: bool = False, focused: bool = True,
            active: bool = True, listen: bool = True, last_before: bool = False) -> int:
        """A text box of the game's own class: its text, limit and flags; listening for keys first
        (or after a listener the dispatch stops at, when last_before)."""
        box = self.alloc(0x80)
        parent = self.alloc(0x20)
        buf = self.alloc(max(limit, len(text)) + 1)
        mu = self.mu
        mu.mem_write(box, struct.pack("<II", self.vtable, 0x77))
        mu.mem_write(box + 0x1C, struct.pack("<I", parent))
        mu.mem_write(parent + 8, b"\x01" if active else b"\x00")
        mu.mem_write(box + 0x24, b"\x01" + (b"\x01" if focused else b"\x00"))
        mu.mem_write(box + 0x28, struct.pack("<i", limit))
        mu.mem_write(box + 0x2C, b"\x01" + (b"\x01" if digits else b"\x00"))
        mu.mem_write(box + 0x30, struct.pack("<I", buf))
        mu.mem_write(buf, text + b"\0")
        if listen:
            head = self.dword(self.list)
            if last_before:
                other = self.alloc(0x40)
                stop = self.alloc(0x10)
                mu.mem_write(stop, struct.pack("<IIII", other, 2, 1, 0))      # a last listener, then the box
                node = self.alloc(0x10)
                mu.mem_write(node, struct.pack("<IIII", box, 3, 0, head))
                mu.mem_write(stop + 12, struct.pack("<I", node))
                mu.mem_write(self.list, struct.pack("<I", stop))
            else:
                node = self.alloc(0x10)
                mu.mem_write(node, struct.pack("<IIII", box, 3, 0, head))
                mu.mem_write(self.list, struct.pack("<I", node))
        return box

    def clear_listeners(self) -> None:
        self.mu.mem_write(self.list, b"\0\0\0\0")

    def text(self, box: int) -> bytes:
        buf = self.dword(box + 0x30)
        return bytes(self.mu.mem_read(buf, 0x800)).split(b"\0")[0]

    def raw(self, box: int, n: int) -> bytes:
        return bytes(self.mu.mem_read(self.dword(box + 0x30), n))

    # -- the key -----------------------------------------------------------------------------------
    def press(self, sym: int, mod: int = 0, repeat: int = 0) -> dict:
        """One SDL_KEYDOWN through the pump's case: {"to": "next event" | "game", ...}."""
        mu = self.mu
        esp = se.STACK_TOP - 0x30000
        frame = bytearray(0x100)
        event = self.sym - 0x14
        struct.pack_into("<I", frame, event, 0x300)
        frame[self.sym - 7] = repeat
        struct.pack_into("<IH", frame, self.sym, sym, mod)
        mu.mem_write(esp, bytes(frame))
        mu.reg_write(UC_X86_REG_ESP, esp)
        mu.reg_write(UC_X86_REG_EAX, 0x300)
        mu.reg_write(UC_X86_REG_EBX, 0)
        mu.reg_write(UC_X86_REG_ESI, 0x5E5E5E5E)
        mu.reg_write(UC_X86_REG_EDI, 0x0A)
        back = self.site + 10
        hit: dict = {}

        def stop(uc, address, size, user):
            if address in (self.cont, back):
                hit["at"] = address
                uc.emu_stop()

        h = mu.hook_add(UC_HOOK_CODE, stop)
        try:
            self.machine.stop_at = None
            self.machine.error = None
            mu.emu_start(self.site, 0, count=5_000_000)
        finally:
            mu.hook_del(h)
        if self.machine.error:
            raise AssertionError(self.machine.error)
        assert hit.get("at") in (self.cont, back), hit
        assert mu.reg_read(UC_X86_REG_ESP) == esp
        assert (mu.reg_read(UC_X86_REG_EBX), mu.reg_read(UC_X86_REG_ESI), mu.reg_read(UC_X86_REG_EDI)) \
            == (0, 0x5E5E5E5E, 0x0A)
        assert not self.clip.open, "the clipboard was left open"
        if hit["at"] == self.cont:
            return {"to": "next event"}
        flags = mu.reg_read(UC_X86_REG_EFLAGS)
        return {"to": "game", "ecx": mu.reg_read(UC_X86_REG_ECX), "eax": mu.reg_read(UC_X86_REG_EAX),
                "zf": bool(flags & 0x40), "sf": bool(flags & 0x80), "of": bool(flags & 0x800),
                "cf": bool(flags & 1)}

    def paste(self, **kw) -> dict:
        return self.press(ord("v"), KMOD_LCTRL, **kw)

    def copy(self) -> dict:
        return self.press(ord("c"), KMOD_LCTRL)

    def cut(self) -> dict:
        return self.press(ord("x"), KMOD_LCTRL)

    # -- the Unicode Text companion's answer -------------------------------------------------------
    def set_glyphs_utf8(self, value: int) -> None:
        """Make VVFP Unicode Text.dll's VvfpGlyphsUtf8() answer `value` (the later stage answers 1)."""
        module = self.machine.modules["vvfp unicode text.dll"]
        at = module.exports["VvfpGlyphsUtf8"]
        self.mu.mem_write(at, b"\xB8" + struct.pack("<I", value) + b"\xC3")

    def give_insert(self) -> list:
        """Give VVFP Unicode Text.dll a VvfpBoxInsertUtf8(box, utf8) export, as the later stage has (PR #676):
        here it appends the text to the box's buffer up to the limit and answers 1.  Returns its calls."""
        module = self.machine.modules["vvfp unicode text.dll"]
        if getattr(self, "_insert_at", None):
            module.exports["VvfpBoxInsertUtf8"] = self._insert_at
            self.insert_calls.clear()
            return self.insert_calls
        at = self._insert_at = self.alloc(16)
        self.mu.mem_write(at, b"\xC2\x08\x00")                    # ret 8 (stdcall, two arguments)
        module.exports["VvfpBoxInsertUtf8"] = at
        self.insert_calls = []

        def insert(uc, address, size, user):
            if address != at:
                return
            esp = uc.reg_read(UC_X86_REG_ESP)
            box, text = struct.unpack("<II", uc.mem_read(esp + 4, 8))
            raw = bytes(uc.mem_read(text, 0x1000)).split(b"\0")[0]
            self.insert_calls.append((box, raw))
            buf = self.dword(box + 0x30)
            have = bytes(uc.mem_read(buf, 0x800)).split(b"\0")[0]
            limit = struct.unpack("<i", uc.mem_read(box + 0x28, 4))[0]
            uc.mem_write(buf, (have + raw)[:limit] + b"\0")
            uc.reg_write(UC_X86_REG_EAX, 1)

        self.mu.hook_add(UC_HOOK_CODE, insert, begin=at, end=at)
        return self.insert_calls

    def take_insert(self) -> None:
        self.machine.modules["vvfp unicode text.dll"].exports.pop("VvfpBoxInsertUtf8", None)

    def type_text(self, utf8: bytes, text_site: int, post: int, skip: int, offset: int):
        """SDL_TEXTINPUT through the Unicode Text companion's detour: ("post", char) or ("skip", None)."""
        mu = self.mu
        esp = se.STACK_TOP - 0x30000
        frame = bytearray(0x100)
        frame[offset:offset + len(utf8) + 1] = utf8 + b"\0"
        mu.mem_write(esp, bytes(frame))
        mu.reg_write(UC_X86_REG_ESP, esp)
        mu.reg_write(UC_X86_REG_EBX, 0)
        hit: dict = {}

        def stop(uc, address, size, user):
            if address in (post, skip):
                hit["at"] = address
                uc.emu_stop()

        h = mu.hook_add(UC_HOOK_CODE, stop)
        try:
            self.machine.stop_at = None
            mu.emu_start(text_site, 0, count=200_000)
        finally:
            mu.hook_del(h)
        if hit.get("at") == skip:
            return "skip", None
        assert hit.get("at") == post, hit
        return "post", struct.unpack("<3I", mu.mem_read(mu.reg_read(UC_X86_REG_ESP), 12))[2]

    def eip(self) -> int:
        return self.mu.reg_read(UC_X86_REG_EIP)
