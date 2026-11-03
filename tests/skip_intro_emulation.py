"""Run the intro story of A New Home and The Lost Children in unicorn, with or without "VVFP Skip Intro.dll".

The build is started as the game starts it (tests/startup_emulation.py: the stub, VVFP Startup.dll, every shipped
companion's VvfpStartup) -- or, for the stock comparison, the stock executable is only mapped.  Then the game's
own screen manager (VV1 0x41B350, VV2 0x423D70) is called once per frame with the game state at the story's
first page, exactly as the game's main loop calls it: it builds the story pages with their own constructors,
activates the page of the current state and runs its update.  A click is the game's own: the mouse press goes to
the page's own event slot (a click anywhere), a click on a button goes to the button's own event slot (its hit
test, then message 8 to the page).

Only what lies outside the game's own logic is answered here (STUBS): the allocator (an arena), the clock (one
tick per frame), the renderer, textures and fonts (fixed sizes), sound and music (recorded), the text table's
lookup (the table's own English, read from the image), the game object (a zeroed block with its state field) and
the game's per-frame tick after the screen.  Everything else -- the page constructors, the button constructor,
its rectangle from its art, the label, the child list, the event manager registration, the hit test, the stock
updates and button slots, and the companion -- runs as machine code.
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

from unicorn import UC_HOOK_CODE, UcError
from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EDX, UC_X86_REG_EIP,
                               UC_X86_REG_ESP)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import startup_emulation as se  # noqa: E402

ARENA = 0x50000000
ARENA_SIZE = 0x00400000
RETURN = se.CRT_RETURN_SENTINEL          # a hlt: where every call made from here returns
SKIP_ID = 0x5C1A
SCREEN = (800, 600)

# Per game: the screen manager, its page fields, the game state field, the story's first state, the pages
# (state, vtable, the last page?), the button art name and its frame strip size (the art's own png:
# main_wide_button2.png 388 x 32, popup_button1.png 420 x 32, three frames), the Yes/No ids, the text table.
GAMES = {
    "vv1": {
        "manager": 0x41B350, "pages": {0x15: 0x28, 0x16: 0x2C}, "state": 0xACB4, "first": 0x15,
        "vtables": {0x15: 0x4597F4, 0x16: 0x45982C}, "last": 0x16,
        "art": 0x459340, "art_size": (388, 32), "skip_xy": (640, 560), "yes_no": (1, 2),
        "button_vtable": 0x4572C0, "button_event": 0x401760,
        "table": (0x487208, 629, 0x14),
        "page_event": {0x15: 0x41E5D0},
        "last_buttons": (0x2B8, 0x2BC), "last_slot": 0x41EC40,
    },
    "vv2": {
        "manager": 0x423D70, "pages": {0x16: 0x2C, 0x17: 0x30, 0x18: 0x34}, "state": 0x30470, "first": 0x16,
        "vtables": {0x16: 0x476AC4, 0x17: 0x476AFC, 0x18: 0x476B34}, "last": 0x18,
        "art": 0x476378, "art_size": (420, 32), "skip_xy": (640, 550), "yes_no": (1, 2),
        "button_vtable": 0x4742C0, "button_event": 0x401780,
        "table": (0x496300, 0x36C, 12),
        "page_event": {0x16: 0x427DF0, 0x17: 0x428430},
        "last_buttons": (0x1F8, 0x1FC), "last_slot": 0x428B30,
    },
}

# The routines answered here, per game: va -> (name, bytes popped on return).  None = cdecl.
STUBS = {
    "vv1": {
        0x44AF03: ("new", None), 0x44AEAE: ("delete", None),
        0x41D500: ("game", 0), 0x402F70: ("clock", 0),
        0x408090: ("renderer", 0), 0x4081F0: ("screen_w", 0), 0x408200: ("screen_h", 0),
        0x408370: ("fast", 0), 0x408150: ("fill", 0x14),
        0x409ED0: ("texture", 4), 0x40A770: ("texture_w", 0), 0x40A780: ("texture_h", 0),
        0x430BC0: ("sound", 0), 0x431470: ("play", 4), 0x430700: ("music", 8),
        0x433980: ("text", 0), 0x433970: ("lookup", 4),
        0x41BFC0: ("game_tick", 0),
    },
    "vv2": {
        0x467F83: ("new", None), 0x467F2E: ("delete", None),
        0x426D40: ("game", 0), 0x403200: ("clock", 0),
        0x408320: ("renderer", 0), 0x408480: ("screen_w", 0), 0x408490: ("screen_h", 0),
        0x408600: ("fast", 0), 0x4083E0: ("fill", 0x14),
        0x40A0D0: ("texture", 4), 0x40A970: ("texture_w", 0), 0x40A980: ("texture_h", 0),
        0x43E460: ("sound", 0), 0x43F010: ("play", 4), 0x43DC80: ("music", 8),
        0x441690: ("text", 0), 0x441680: ("lookup", 4),
        0x424C40: ("game_tick", 0),
    },
}


# SDL calls the story's own teardown makes (a page's destructor frees its pictures): answered as no-ops.
SDL_IMPORTS = ("SDL_FreeSurface", "SDL_DestroyTexture")


def register() -> None:
    """Before a machine is built: the SDL calls above return at once (cdecl)."""
    for name in SDL_IMPORTS:
        se.EXTRA_IMPORTS.setdefault(name, (0, lambda mc, arg, ret: ret(0)))


class Intro:
    """One machine (a published build after WinMain, or the stock executable mapped) and its story."""

    def __init__(self, machine, game: str) -> None:
        self.machine = machine
        self.mu = machine.mu
        self.game = game
        self.g = GAMES[game]
        self.mu.mem_map(ARENA, ARENA_SIZE)
        self.next = ARENA + 0x1000
        self.tick = 1000
        self.fast = 0
        self.sounds: list[int] = []
        self.music = 0
        self.fills = 0
        self.deleted: list[int] = []
        self.textures: dict[int, str] = {}
        self.unknown: list[int] = []
        self.game_obj = self.alloc(self.g["state"] + 0x1000)
        self.renderer = self.alloc(0x400)
        self.renderer_impl = self.alloc(0x1000)
        self.font = self.alloc(0x400)
        self.put(self.renderer, self.renderer_impl)
        self.put(self.renderer_impl + 0x5C, self.font)
        self.sound_obj = self.alloc(0x400)
        self.text_obj = self.alloc(0x400)
        self.manager = self.alloc(0x100)
        self.mu.mem_write(self.manager + 4, struct.pack("<I", self.game_obj))
        self.state = self.g["first"]
        self._english = self._read_table()
        self._strings: dict[int, int] = {}
        for va, (name, popped) in STUBS[game].items():
            self.mu.hook_add(UC_HOOK_CODE, self._stub, (name, popped), begin=va, end=va)

    # -- memory ------------------------------------------------------------------------------------
    def alloc(self, n: int) -> int:
        at = self.next
        self.next = (self.next + max(n, 1) + 15) & ~15
        assert self.next < ARENA + ARENA_SIZE
        self.mu.mem_write(at, b"\0" * max(n, 1))
        return at

    def dword(self, va: int) -> int:
        return struct.unpack("<I", self.mu.mem_read(va, 4))[0]

    def byte(self, va: int) -> int:
        return self.mu.mem_read(va, 1)[0]

    def put(self, va: int, value: int) -> None:
        self.mu.mem_write(va, struct.pack("<I", value & 0xFFFFFFFF))

    def cstr(self, va: int) -> str:
        return bytes(self.mu.mem_read(va, 256)).split(b"\0")[0].decode("cp1252")

    @property
    def state(self) -> int:
        return self.dword(self.game_obj + self.g["state"])

    @state.setter
    def state(self, value: int) -> None:
        self.put(self.game_obj + self.g["state"], value)

    def _read_table(self) -> dict[int, int]:
        va, count, stride = self.g["table"]
        out = {}
        for i in range(count):
            rid, en = struct.unpack("<II", self.mu.mem_read(va + i * stride, 8))
            out.setdefault(rid, en)
        return out

    # -- the routines answered here ----------------------------------------------------------------
    def _stub(self, mu, address, size, user):
        name, popped = user
        sp = mu.reg_read(UC_X86_REG_ESP)
        ret_to = self.dword(sp)
        arg = lambda k: self.dword(sp + 4 + 4 * k)   # noqa: E731
        ecx = mu.reg_read(UC_X86_REG_ECX)
        value = 0
        if name == "new":
            value = self.alloc(arg(0))
        elif name == "delete":
            self.deleted.append(arg(0))
        elif name == "game":
            value = self.game_obj
        elif name == "clock":
            value = self.tick
        elif name == "renderer":
            value = self.renderer
        elif name == "screen_w":
            value = SCREEN[0]
        elif name == "screen_h":
            value = SCREEN[1]
        elif name == "fast":
            value = self.fast
        elif name == "texture":
            # the image's texture: [image+4]; its size answers texture_w / texture_h
            tex = self.alloc(0x20)
            art = self.cstr(arg(0))
            self.textures[tex] = art
            self.put(ecx + 4, tex)
        elif name == "texture_w":
            value = self._texture_size(ecx)[0]
        elif name == "texture_h":
            value = self._texture_size(ecx)[1]
        elif name == "sound":
            value = self.sound_obj
        elif name == "play":
            self.sounds.append(arg(0))
        elif name == "music":
            self.music += 1
        elif name == "text":
            value = self.text_obj
        elif name == "lookup":
            value = self._english.get(arg(0), 0)
        elif name == "fill":
            self.fills += 1
        elif name == "game_tick":
            pass
        mu.reg_write(UC_X86_REG_EAX, value & 0xFFFFFFFF)
        mu.reg_write(UC_X86_REG_ESP, sp + 4 + (popped or 0))
        mu.reg_write(UC_X86_REG_EIP, ret_to)

    def _texture_size(self, tex: int) -> tuple[int, int]:
        art = self.textures.get(tex, "")
        art_name = self.cstr(self.g["art"])
        if art == art_name:
            return self.g["art_size"]
        return SCREEN

    # -- calls -------------------------------------------------------------------------------------
    def call(self, va: int, this: int = 0, args: tuple = (), count: int = 5_000_000) -> int:
        """thiscall (or cdecl with this=0) `va`; returns eax."""
        mu = self.mu
        esp = se.STACK_TOP - 0x40000
        frame = struct.pack("<I", RETURN) + b"".join(struct.pack("<I", a & 0xFFFFFFFF) for a in args)
        esp -= len(frame)
        mu.mem_write(esp, frame)
        mu.reg_write(UC_X86_REG_ESP, esp)
        mu.reg_write(UC_X86_REG_ECX, this)
        mu.reg_write(UC_X86_REG_EDX, 0)
        self.machine.stop_at = None
        self.machine.error = None
        try:
            mu.emu_start(va, RETURN, count=count)
        except UcError as exc:
            sp = mu.reg_read(UC_X86_REG_ESP)
            trail = [hex(v) for v in struct.unpack("<64I", mu.mem_read(sp, 256)) if 0x401000 <= v < 0x480000]
            raise AssertionError(f"emulation fault {exc} at {mu.reg_read(UC_X86_REG_EIP):#x} "
                                 f"(return addresses on the stack: {trail[:12]})") from None
        if self.machine.error:
            raise AssertionError(self.machine.error)
        eip = mu.reg_read(UC_X86_REG_EIP)
        assert eip == RETURN, f"stopped at {eip:#x}"
        self.machine.accesses.clear()
        return mu.reg_read(UC_X86_REG_EAX)

    # -- the story ---------------------------------------------------------------------------------
    def frame(self) -> None:
        """One frame of the game's main loop on the story: the screen manager, then the clock."""
        self.call(self.g["manager"], self.manager)
        self.tick += 1

    def page(self, state: int) -> int:
        return self.dword(self.manager + self.g["pages"][state])

    def active(self, page: int) -> bool:
        return self.byte(self.dword(page + 4)) != 0

    def children(self, page: int) -> list[int]:
        """The page's child widgets, as the page's draw walks them ([page+4]+0x18: {widget, next})."""
        out, node = [], self.dword(self.dword(page + 4) + 0x18)
        while node:
            out.append(self.dword(node))
            node = self.dword(node + 4)
        return out

    def skip_button(self, page: int) -> int | None:
        """The page's child whose real button has our id (the button object is at [child+0x10])."""
        for child in self.children(page):
            real = self.dword(child + 0x10)
            if real and self.dword(real + 4) == SKIP_ID:
                return child
        return None

    def rect(self, child: int) -> tuple[int, int, int, int]:
        real = self.dword(child + 0x10)
        return struct.unpack("<4i", self.mu.mem_read(real + 0x10, 16))

    def label(self, child: int) -> str:
        real = self.dword(child + 0x10)
        return self.cstr(self.dword(real + 0x40))

    def mouse(self, child: int, event: int, x: int, y: int) -> int:
        """The game's own button event slot (hit test, press, release -> message 8 to its page)."""
        real = self.dword(child + 0x10)
        return self.call(self.g["button_event"], real, (event, x, y)) & 0xFF

    def click_button(self, child: int, x: int, y: int) -> None:
        self.mouse(child, 2, x, y)
        self.mouse(child, 3, x, y)

    def click_anywhere(self, page: int) -> None:
        """A press anywhere on the page: its own event slot (vtable slot 1), as the event manager sends it."""
        slot1 = self.dword(self.dword(page) + 4)
        self.call(slot1, page, (2, 100, 100))

    def run_until(self, done, limit: int = 400) -> int:
        for n in range(limit):
            if done():
                return n
            self.frame()
        raise AssertionError("the story did not get there")

    def question_up(self) -> bool:
        last = self.page(self.g["last"])
        yes_field, no_field = self.g["last_buttons"]
        kids = self.children(last)
        return self.dword(last + yes_field) in kids and self.dword(last + no_field) in kids

    def answer(self, yes: bool) -> None:
        """A click on the last page's Yes or No: the button's own event slot, which reports to the page."""
        last = self.page(self.g["last"])
        child = self.dword(last + self.g["last_buttons"][0 if yes else 1])
        x0, y0, x1, y1 = self.rect(child)
        self.click_button(child, (x0 + x1) // 2, (y0 + y1) // 2)

    def game_bytes(self) -> bytes:
        return bytes(self.mu.mem_read(self.game_obj, self.g["state"] + 0x1000))
