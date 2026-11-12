"""Run a published build's island-event dialog in unicorn with "VVFP Scrolling Popups.dll" installed.

Builds on tests/unicode_text_emulation.py's FontRun: the build is started as the game starts it (the stub, VVFP
Startup.dll, every companion's VvfpStartup), the game's own two fonts are built by the game's own code from the
stock pictures, and the game's own image manager loads every picture it is asked for (research/game-images).  On
that machine this module makes an island-event dialog the way the game's constructor does:

  * the dialog's base constructor (the window node, the panel fields) runs as the game's code, then the dialog's own
    vtable and the fields the constructor sets before the panel is sized (text box at +0x850/+0x854/+0x858, the
    title, the body text at +0x58, the font +0x82C, no villager picture);
  * the constructor's own tail runs from the instruction that loads the panel picture through the sizer call (the
    companion's size site) to the placing of the buttons (`mov byte [esi+0x4C], 1`), with edi = the panel height the
    constructor computed by its own formula (text height by the game's justified paragraph, measure only);
  * the buttons and the event are small stand-ins whose virtual methods answer from Python (their size, their
    position); the event answers "two choices" or not;

and then draws the dialog with the game's own panel draw (the 9-slice, then the dialog's body draw, which reaches
the companion's draw site), sends mouse events through the event pump's call site, and wheel events to the event
watch the companion registered with SDL_AddEventWatch.  The clip test is the game's own (FontRun's always-on-screen
answer is switched off), so the clip rectangle the companion sets is what cuts the drawn text.

Every SDL_UpperBlit is recorded (source, source rect, target, position); `picture()` composites them, in order, into
an RGBA picture of the screen.
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

from unicorn import UC_HOOK_CODE
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDI, UC_X86_REG_EDX, UC_X86_REG_EIP,
    UC_X86_REG_ESI, UC_X86_REG_ESP,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import startup_emulation as se  # noqa: E402
import unicode_text_emulation as ute  # noqa: E402

CODE = 0x0C000000                 # the stand-ins' methods: each address answered from Python
SDL_MODULE = 0x0C800000           # "SDL2.dll" as the companion finds it, with SDL_AddEventWatch
FRAME = se.STACK_TOP - 0x40000    # the constructor's stack frame for its tail

# Per game: the dialog constructor, its base constructor (this, fade flag), the base draw (panel + body), the body
# draw, the tail [start, the `mov byte [esi+0x4C], 1` it ends at), the frame slots of the image manager and the
# event, the panel picture's fetch arguments, the OK and choice button picture ids, the centred text draw, the
# panel's width, the text box (x, width) and the title's x, the ctx holder global, the image manager and its fetch,
# and the pump's mouse call site and its target.
GAMES = {
    "vv3": dict(ctor=0x4192F0, base=0x40E100, base_draw=None, body=0x418510, tail=0x41982B, frame_mgr=0x10,
                frame_event=0x54, ok_id=0x10, choice_id=0x04, centred=0x40A070, width=0x200, screen=(800, 600),
                holder=0x4B34A8, app=0x4B309C, mgr=0x42E9D0, lookup=0x42E6F0, get=0x42EA80, mouse=0x40451E, dispatch=0x4020A0, justify=0x40A0C0, draw_site=0x418591,
                size_site=0x41983F, sizer=0x40DDD0, single=0x4197D6, single_holder=0x1C, add_child=0x40C1F0),
    "vv4": dict(ctor=0x417790, base=0x40DD00, base_draw=None, body=0x416EC0, tail=0x417CD8, frame_mgr=0x14,
                frame_event=0x58, ok_id=0x82, choice_id=0x83, centred=0x409BE0, width=0x200, screen=(800, 600),
                holder=0x4CB928, app=0x4CB51C, mgr=0x44CCF0, lookup=0x44C8A0, get=0x44CB80, mouse=0x404B02, dispatch=0x402320, justify=0x409C30, draw_site=0x416F4C,
                size_site=0x417CEF, sizer=0x40DE20, single=0x417C83, single_holder=0x20, add_child=0x40C190),
    "vv5": dict(ctor=0x418020, base=0x40E1F0, base_draw=None, body=0x417660, tail=0x41855F, frame_mgr=0x14,
                frame_event=0x58, ok_id=0x75, choice_id=0x65, centred=0x409EB0, width=0x2C0, screen=(1024, 768),
                holder=0x4DB0E8, app=0x4DACE0, mgr=0x44FBB0, lookup=0x44F760, get=0x44FA40, mouse=0x404A92, dispatch=0x4022D0, justify=0x409F00, draw_site=0x4176E9,
                size_site=0x418573, sizer=0x40E310, single=0x41850A, single_holder=0x20, add_child=0x40C680),
}


def _map_rgba(mc, arg, ret):
    """SDL_MapRGBA(format, r, g, b, a): the colour in the format's masks."""
    fmt = arg(0)
    masks = struct.unpack("<4I", mc.mu.mem_read(fmt + 0x0C, 16))
    shifts = bytes(mc.mu.mem_read(fmt + 0x20, 4))
    value = 0
    for k, c in enumerate((arg(1) & 0xFF, arg(2) & 0xFF, arg(3) & 0xFF, arg(4) & 0xFF)):
        value |= (c << shifts[k]) & masks[k]
    ret(value)


def _tables() -> dict:
    return json.loads((ROOT / "data" / "font_glyph_tables.json").read_text(encoding="utf-8"))


class Dialog:
    """One published build of `game` with the island-event dialog to make, draw and click."""

    def __init__(self, game: str, selection=None, font: str = "ldwarialbold") -> None:
        self.game = game
        self.g = dict(GAMES[game])
        self.watch = None
        se.EXTRA_IMPORTS.setdefault("SDL_MapRGBA", (0, _map_rgba))
        self.run = ute.FontRun(game, "collection_progression",
                               tuple(selection) if selection else (f"{game}_scrolling_popups",), _tables())
        self.run.r.clip = None            # the game's own clip test, not FontRun's always-on-screen answer
        # Every picture the game's loader loads, by file name (the companion builds its own strips of the scrollbar
        # pictures from the game's files, so each of those names may be loaded more than once).
        self.loaded: dict[str, set] = {}
        load = self.run._picture

        def _picture(path: str) -> int:
            surface = load(path)
            self.loaded.setdefault(path.replace("/", "\\").split("\\")[-1].lower(), set()).add(surface)
            return surface

        self.run._picture = _picture
        self.m = self.run.m
        self.mu = self.m.mu
        self._install_sdl_answers()
        tables = _tables()
        spacing = tables["games"][game]["fonts"][font]["spacing"]
        self.font = self.run.build_font(font, spacing)
        self.mu.mem_map(CODE, 0x10000)
        self.mu.mem_write(CODE, b"\xC3" * 0x10000)
        self.mu.mem_map(SDL_MODULE, 0x1000)
        self.mu.mem_write(SDL_MODULE, b"\xC3" * 0x1000)
        self.answers: dict[int, tuple] = {}
        self._next_code = CODE
        self.mu.hook_add(UC_HOOK_CODE, self._answer, begin=CODE, end=CODE + 0x10000)
        self.mu.hook_add(UC_HOOK_CODE, self._dispatch, begin=self.g["dispatch"], end=self.g["dispatch"])
        self.passed: list[tuple[int, int, int]] = []    # mouse events the game's dispatcher received
        self.mu.hook_add(UC_HOOK_CODE, self._add_child, begin=self.g["add_child"], end=self.g["add_child"])
        self.mu.hook_add(UC_HOOK_CODE, self._at_size_site, begin=self.g["size_site"], end=self.g["size_site"])
        self.mu.hook_add(UC_HOOK_CODE, self._at_size, begin=self.g["sizer"], end=self.g["sizer"])
        self.size_requests: list[int] = []
        self.stock_heights: list[int] = []
        w, h = self.g["screen"]
        self.screen = self.run._new_surface(w, h, 0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000)
        heap = self.m.font_heap
        self.ctx = heap.alloc(0x400)
        self.mu.mem_write(self.ctx + 0x08, struct.pack("<ii", w, h))
        self.mu.mem_write(self.ctx + 0x30, struct.pack("<I", self.screen))
        self.mu.mem_write(self.ctx + 0x5C, struct.pack("<I", self.font))
        self.mu.mem_write(self.ctx + 0x60, struct.pack("<4i", 0, 0, w, h))
        self.holder = heap.alloc(16)
        self.mu.mem_write(self.holder, struct.pack("<I", self.ctx))
        self.mu.mem_write(self.g["holder"], struct.pack("<I", self.holder))
        self.manager = self.run._call(self.g["mgr"], 0)
        # The game object (its vtable[9] says which screen is up; a panel draws only on the screen it was made on).
        self.app = self._object({0x24: (lambda a: 7, 0)})
        self.mu.mem_write(self.g["app"], struct.pack("<I", self.app))
        self.colour = 0                   # the dialogs' colour global: never written, so 0 (the font's own)
        self.clip_log: list[tuple] = []

    # -- SDL2.dll as the companion finds it -------------------------------------------------------------------
    def _install_sdl_answers(self) -> None:
        """GetModuleHandleA("SDL2.dll") and GetProcAddress(it, "SDL_AddEventWatch"): the watch is kept."""
        m = self.m
        original = m._import
        harness = self

        def _import(name: str) -> None:
            mu = m.mu
            sp = mu.reg_read(UC_X86_REG_ESP)

            def arg(k):
                return struct.unpack("<I", mu.mem_read(sp + 4 + 4 * k, 4))[0]

            def ret(value, pop):
                to = struct.unpack("<I", mu.mem_read(sp, 4))[0]
                mu.reg_write(UC_X86_REG_EAX, value & 0xFFFFFFFF)
                mu.reg_write(UC_X86_REG_ESP, sp + 4 + pop)
                mu.reg_write(UC_X86_REG_EIP, to)

            if name == "GetModuleHandleA" and arg(0):
                text = bytes(mu.mem_read(arg(0), 64)).split(b"\0")[0].decode("latin-1")
                if text.lower() == "sdl2.dll":
                    ret(SDL_MODULE, 4)
                    return
            if name == "GetProcAddress" and arg(0) == SDL_MODULE:
                proc = bytes(mu.mem_read(arg(1), 64)).split(b"\0")[0].decode("latin-1")
                ret(harness._method(harness._add_watch, 0) if proc == "SDL_AddEventWatch" else 0, 8)
                return
            original(name)

        m._import = _import

    def _add_watch(self, args):
        self.watch = args[0]
        return 0

    # -- stand-in methods ----------------------------------------------------------------------------------------
    def _method(self, fn, pop: int, this: bool = False) -> int:
        """A code address that, when called, answers fn(args) (or fn(args, ecx)) -> eax and pops `pop` bytes."""
        at = self._next_code
        self._next_code += 16
        self.answers[at] = (fn, pop, this)
        return at

    def _answer(self, mu, address, size, user):
        entry = self.answers.get(address)
        if entry is None:
            return
        fn, pop, wants_this = entry
        sp = mu.reg_read(UC_X86_REG_ESP)
        args = list(struct.unpack("<8I", mu.mem_read(sp + 4, 32)))
        value = fn(args, mu.reg_read(UC_X86_REG_ECX)) if wants_this else fn(args)
        to = struct.unpack("<I", mu.mem_read(sp, 4))[0]
        mu.reg_write(UC_X86_REG_EAX, (value or 0) & 0xFFFFFFFF)
        mu.reg_write(UC_X86_REG_ESP, sp + 4 + pop)
        mu.reg_write(UC_X86_REG_EIP, to)

    def _dispatch(self, mu, address, size, user):
        sp = mu.reg_read(UC_X86_REG_ESP)
        to, kind, x, y = struct.unpack("<4I", mu.mem_read(sp, 16))
        self.passed.append((kind, x, y))
        mu.reg_write(UC_X86_REG_ESP, sp + 4 + 12)
        mu.reg_write(UC_X86_REG_EIP, to)

    def _add_child(self, mu, address, size, user):
        """The window's add-child (thiscall(window; child) ret 4): the stand-in buttons need no window list."""
        sp = mu.reg_read(UC_X86_REG_ESP)
        to = struct.unpack("<I", mu.mem_read(sp, 4))[0]
        mu.reg_write(UC_X86_REG_ESP, sp + 8)
        mu.reg_write(UC_X86_REG_EIP, to)

    def _at_size_site(self, mu, address, size, user):
        """The constructor's panel height as it makes the sizer call (the stock formula's result)."""
        sp = mu.reg_read(UC_X86_REG_ESP)
        self.stock_heights.append(struct.unpack("<i", mu.mem_read(sp + 8, 4))[0])

    def _at_size(self, mu, address, size, user):
        """The height the sizer is given (after the companion, when it caps it)."""
        sp = mu.reg_read(UC_X86_REG_ESP)
        self.size_requests.append(struct.unpack("<i", mu.mem_read(sp + 12, 4))[0])

    def _object(self, methods: dict[int, tuple]) -> int:
        """An object whose vtable slot (byte offset) -> (fn, pop[, wants this])."""
        heap = self.m.font_heap
        vtable = heap.alloc(0x80)
        for slot, spec in methods.items():
            self.mu.mem_write(vtable + slot, struct.pack("<I", self._method(*spec)))
        obj = heap.alloc(0x40)
        self.mu.mem_write(obj, struct.pack("<I", vtable))
        return obj

    # -- helpers --------------------------------------------------------------------------------------------------
    def u32(self, va: int) -> int:
        return struct.unpack("<I", self.mu.mem_read(va, 4))[0]

    def i32(self, va: int) -> int:
        return struct.unpack("<i", self.mu.mem_read(va, 4))[0]

    def put(self, va: int, *values: int) -> None:
        self.mu.mem_write(va, struct.pack("<%di" % len(values), *values))

    def picture_of(self, image_id: int) -> tuple[int, int, int]:
        """The game's image `image_id` (its manager's fetch): (image, width, height) of one frame (the image table's
        columns and rows)."""
        inner = self.u32(self.manager)
        image = self.run._call(self.g["get"], inner, image_id)
        loaded = self.u32(image + 4)
        surface = self.u32(loaded)
        entry = self.run._call(self.g["lookup"], 0, image_id)
        columns, rows = max(self.i32(entry + 8), 1), max(self.i32(entry + 12), 1)
        return image, self.i32(surface + 8) // columns, self.i32(surface + 12) // rows

    def justify_height(self, text_va: int, width: int) -> int:
        return self.run._call(self.g["justify"], self.holder, text_va, 0, 0, width, self.colour, self.font, 1)

    def companion_export(self, name: str) -> int:
        dll = next(m for k, m in self.m.modules.items() if "scrolling" in k)
        return self.run._call(dll.exports[name], 0)

    VIEW = ("shown", "box_x", "box_y", "box_w", "box_h", "content_w", "content_h", "vbar", "hbar", "vx", "vy", "vh",
            "arrow_h", "hx", "hy", "hw", "hh", "line", "sx", "sy")

    def view(self) -> dict:
        """The companion's view of the dialog it drew last (VvfpScrollingPopupsView)."""
        dll = next(m for k, m in self.m.modules.items() if "scrolling" in k)
        out = self.m.font_heap.alloc(4 * len(self.VIEW))
        n = self.run._call(dll.exports["VvfpScrollingPopupsView"], 0, out, len(self.VIEW))
        values = struct.unpack("<%di" % n, self.mu.mem_read(out, 4 * n))
        return dict(zip(self.VIEW, values))

    def scroll(self) -> tuple[int, int]:
        v = self.view()
        return v["sx"], v["sy"]

    ART_FILES = {"up": "uparrowbutton.png", "down": "downarrowbutton.png", "track": "verticalscrolltrack.png",
                 "knob": "verticalscrollknob.png", "wide": "wideslider2.png", "handle": "sliderhandle.png"}

    def art_surfaces_by_name(self) -> dict:
        """The scrollbar pictures' SDL surfaces, by name: every surface the game's loader made from that file."""
        return {name: self.loaded.get(file, set()) for name, file in self.ART_FILES.items()}

    def art_surfaces(self) -> set:
        return set().union(*self.art_surfaces_by_name().values())

    def panel_surfaces(self) -> set:
        """The panel's 9-slice picture's surface (the dialog's +0x3C: its picture at +0x14)."""
        nine = self.u32(self.dialog + 0x3C)
        image = self.u32(nine + 0x14) if nine else 0
        return {self.u32(self.u32(image + 4))} if image else set()

    def art_blits(self, blits) -> dict:
        by_surface = {s: n for n, ss in self.art_surfaces_by_name().items() for s in ss}
        out: dict = {}
        for b in blits:
            if b[0] in by_surface:
                out.setdefault(by_surface[b[0]], []).append(b)
        return out

    def first_line(self) -> tuple:
        """The first drawn text line of the body: its blits' (source rect, x) in order -- what it says."""
        bx, by, bw = self.box()
        blits = self.draw(with_panel=False)
        skip = self.art_surfaces() | self.panel_surfaces()
        body = [b for b in blits if b[0] not in skip and b[3][1] >= by - 2]
        if not body:
            return ()
        top = min(b[3][1] for b in body)
        return tuple((b[1], b[3][0]) for b in body if b[3][1] < top + 4)

    # -- the dialog -------------------------------------------------------------------------------------------------
    def make(self, text: bytes, choices: bool = False, title: bytes = b"The Mysterious Footprints") -> int:
        """A dialog with `text` (and two choice buttons, or OK), laid out by the constructor's own tail."""
        g = self.g
        heap = self.m.font_heap
        mu = self.mu
        self.dialog = d = heap.alloc(0x900)
        self.run._call(g["base"], d, 0)                      # the base constructor, no fade-in
        ctor_code = bytes(mu.mem_read(g["ctor"], 0x80))
        at = ctor_code.find(b"\xC7\x06")
        mu.mem_write(d, ctor_code[at + 2:at + 6])            # the dialog's own vtable (its first `mov [esi], imm`)
        self.choices = choices
        self.event = self._object({0x10: (lambda a: 1 if self.choices else 0, 0)})
        ok_image, ok_w, ok_h = self.picture_of(g["ok_id"])
        ch_image, ch_w, ch_h = self.picture_of(g["choice_id"])
        self.button_size = {"ok": (ok_w, ok_h), "choice": (ch_w, ch_h)}
        self.buttons = {}
        for name, field, (bw, bh) in (("choice_a", 0x85C, self.button_size["choice"]),
                                      ("choice_b", 0x860, self.button_size["choice"]),
                                      ("ok", 0x864, self.button_size["ok"])):
            obj = self._object({
                0x04: (lambda a, this: self.put(this + 0x20, a[0], a[1]), 8, True),  # set position
                0x0C: (lambda a, w=bw: w, 0),
                0x10: (lambda a, h=bh: h, 0),
            })
            mu.mem_write(d + field, struct.pack("<I", obj))
            self.buttons[name] = obj
        self.button_images = {"ok": ok_image, "choice_a": ch_image, "choice_b": ch_image}
        self.text_va = d + 0x58
        mu.mem_write(self.text_va, text[:1999] + b"\0")
        self.title = heap.alloc(len(title) + 1)
        mu.mem_write(self.title, title + b"\0")
        mu.mem_write(d + 0x50, struct.pack("<I", self.event))
        mu.mem_write(d + 0x54, struct.pack("<I", self.title))
        mu.mem_write(d + 0x82C, struct.pack("<I", self.font))
        mu.mem_write(d + 0x834, struct.pack("<I", 0))
        # The constructor's fields before the sizer (no villager picture): title at (width / 2, 0), text box at
        # (0x28, 2 x the font's line height), 0x1B0 wide (The Secret City, The Tree of Life; New Believers' wider
        # panel keeps 0x28 on each side of its box too).
        line = self.justify_height(self._cstr(b"X"), 0x1B0)
        box_w = g["width"] - 0x50
        self.put(d + 0x848, g["width"] // 2, 0, 0x28, 2 * line, box_w)
        # The tail: with OK alone, from the constructor's own measure of the text (its measure site) and height
        # formula; with two choices (whose measures take the event's three texts) from loading the panel picture,
        # with the height the constructor's formula gives (the tallest text: the question here).  Then through the
        # sizer to placing the buttons.
        start, height = g["single"], 0
        if choices:
            self.text_height = max(self.justify_height(self.text_va, box_w), line)
            height = self.text_height + 4 * self.button_size["choice"][1] + self.i32(d + 0x854)
            start = g["tail"]
        tail_end = bytes(mu.mem_read(g["tail"], 0x300)).find(b"\xC6\x46\x4C\x01") + g["tail"]
        frame = FRAME
        mu.mem_write(frame, b"\0" * 0x100)
        mu.mem_write(frame + g["frame_mgr"], struct.pack("<I", self.manager))
        mu.mem_write(frame + g["frame_event"], struct.pack("<I", self.event))
        if not choices:
            mu.mem_write(frame + g["single_holder"], struct.pack("<I", self.holder))
        for reg, value in ((UC_X86_REG_ESP, frame), (UC_X86_REG_ESI, d), (UC_X86_REG_EDI, height),
                           (UC_X86_REG_EBX, 0), (UC_X86_REG_EBP, 0)):
            mu.reg_write(reg, value)
        self.size_requests = []
        self.stock_heights = []
        self.m.stop_at = tail_end
        self.m.error = None
        mu.emu_start(start, tail_end, count=50_000_000)
        self.stock_height = self.stock_heights[-1] if self.stock_heights else None
        if self.m.error or mu.reg_read(UC_X86_REG_EIP) != tail_end:
            raise AssertionError(self.m.error or f"tail stopped at {mu.reg_read(UC_X86_REG_EIP):#x}")
        return d

    def _cstr(self, data: bytes) -> int:
        va = self.m.font_heap.alloc(len(data) + 1)
        self.mu.mem_write(va, data + b"\0")
        return va

    def set_text(self, text: bytes) -> None:
        """The result replacing the question (the click handler writes +0x58 the same way)."""
        self.mu.mem_write(self.text_va, text[:1999] + b"\0")

    def panel(self) -> tuple[int, int, int, int]:
        return struct.unpack("<4i", self.mu.mem_read(self.dialog + 0x14, 16))

    def box(self) -> tuple[int, int, int]:
        return struct.unpack("<3i", self.mu.mem_read(self.dialog + 0x850, 12))

    def button_position(self, name: str) -> tuple[int, int]:
        """Where the constructor put a button (relative to the panel, as its SetPosition is given)."""
        return struct.unpack("<2i", self.mu.mem_read(self.buttons[name] + 0x20, 8))

    def clip(self) -> tuple[int, int, int, int]:
        return struct.unpack("<4i", self.mu.mem_read(self.ctx + 0x60, 16))

    # -- drawing ----------------------------------------------------------------------------------------------------
    def draw(self, with_panel: bool = True) -> list:
        """The dialog's draw as the game makes it: the panel (base draw: its 9-slice, then the body draw), or the
        body draw alone.  Returns the blits; every clip the drawing context held at a blit is in clip_log."""
        self.m.blits = []
        vtable = self.u32(self.dialog)
        if with_panel:
            self.run._call(self.u32(vtable + 0x18), self.dialog)
        else:
            self.run._call(self.g["body"], self.dialog)
        return list(self.m.blits)

    def draw_buttons(self, labels: dict[str, bytes]) -> list:
        """The buttons as the game draws them: their picture's first state at their place, the label centred."""
        frame_draw = {"vv3": 0x409F80, "vv4": 0x409A00, "vv5": 0x409C30}[self.game]
        out = []
        left, top, _r, _b = self.panel()
        for name, label in labels.items():
            x, y = self.button_position(name)
            kind = "ok" if name == "ok" else "choice"
            bw, bh = self.button_size[kind]
            self.m.blits = []
            self.run._call(frame_draw, self.holder, self.button_images[name], left + x, top + y, 0, 0x3F800000)
            self.run._call(self.g["centred"], self.holder, self._cstr(label), left + x + bw // 2,
                           top + y + (bh - 18) // 2, 0xFF000000, self.font)
            out += self.m.blits
        return out

    # -- input ------------------------------------------------------------------------------------------------------
    def mouse(self, kind: int, x: int, y: int) -> bool:
        """One mouse event through the event pump's call site; True when the game's dispatcher received it."""
        mu = self.mu
        site = self.g["mouse"]
        before = len(self.passed)
        manager = self.m.font_heap.alloc(16)
        sp = FRAME - 0x200
        mu.mem_write(sp, struct.pack("<3I", kind, x, y))
        mu.reg_write(UC_X86_REG_ESP, sp)
        mu.reg_write(UC_X86_REG_EAX, manager)
        mu.reg_write(UC_X86_REG_ECX, manager)
        self.m.stop_at = site + 5
        self.m.error = None
        # the call site's own `call` pushes the return address; stop when it returns past it
        mu.emu_start(site, site + 5, count=5_000_000)
        if self.m.error or mu.reg_read(UC_X86_REG_EIP) != site + 5:
            raise AssertionError(self.m.error or f"mouse stopped at {mu.reg_read(UC_X86_REG_EIP):#x}")
        return len(self.passed) > before

    def click(self, x: int, y: int) -> bool:
        a = self.mouse(2, x, y)
        b = self.mouse(3, x, y)
        return a or b

    def wheel(self, notches: int) -> None:
        """SDL_MOUSEWHEEL through the watch the companion registered (y = notches, + is away from the player)."""
        if self.watch is None:
            raise AssertionError("no event watch registered")
        event = self.m.font_heap.alloc(0x40)
        self.mu.mem_write(event, struct.pack("<IIIIii", 0x403, 0, 1, 0, 0, notches))
        self.run._call(self.watch, 0, 0, event)

    # -- pictures ---------------------------------------------------------------------------------------------------
    def picture(self, blits: list, background=(28, 52, 38)) -> tuple[int, int, bytes]:
        w, h = self.g["screen"]
        out = bytearray(bytes(background) + b"\xff") * (w * h)
        for src, rect, _dst, to in blits:
            sw, sh, pitch, pixels, amask, ashift = self.run.surface(src)
            if rect is None:
                rect = (0, 0, sw, sh)
            x1, y1, rw, rh = rect
            dx, dy = to[0], to[1]
            for yy in range(rh):
                ty = dy + yy
                if not 0 <= ty < h:
                    continue
                row = (y1 + yy) * pitch
                for xx in range(rw):
                    tx = dx + xx
                    if not 0 <= tx < w:
                        continue
                    p = struct.unpack_from("<I", pixels, row + (x1 + xx) * 4)[0]
                    a = (p & amask) >> ashift if amask else 255
                    if a == 0:
                        continue
                    o = (ty * w + tx) * 4
                    for k, c in enumerate(((p >> 16) & 0xFF, (p >> 8) & 0xFF, p & 0xFF)):
                        out[o + k] = (c * a + out[o + k] * (255 - a)) // 255
        return w, h, bytes(out)

    def save_picture(self, blits: list, path) -> None:
        from vv_picture_image import Image, encode_png
        w, h, data = self.picture(blits)
        Path(path).write_bytes(encode_png(Image(w, h, bytearray(data))))
