"""The Tree of Life's and New Believers' Options dialog, emulated whole.

A published (or stock) executable is mapped at 0x400000 as the startup loader
leaves it (tests/startup_emulation.py, with "VVFP Difficulty.dll" installed
when the build ships it).  Then the game's own code runs:

* the dialog's constructor (VV4 0x419FA0, VV5 0x41A800): its base widget, its
  tiled frame (the frame object and its sizing, VV4 0x40DE20 / VV5 0x40E310,
  centred on the screen by the game's own 0x401DD0 / 0x401D80), the Done
  button it places from the dialog's own height, and the four Music Tracks
  checkboxes it builds at fixed positions in the dialog;
* the frame's own draw (its vtable slot 3: whole 64-pixel tiles);
* the dialog's draw routine (VV4 0x41A5A0, VV5 0x41ADF0);
* its click handler (VV4 0x41AD60, VV5 0x41B5C0).

Only the leaves are answered here: memory allocation, the image and string
lookups (an image is a handle naming its id; a string is a handle naming its
id), the drawing primitives (recorded, not drawn), the child widgets' own
constructors (recorded with the position the game gives them), and the screen
size (800 x 600, 1024 x 768) through the graphics object the game reads it
from.  Every position and size is therefore the game's own arithmetic.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field

from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EIP, UC_X86_REG_ESP

REGION = 0x50000000          # objects this harness makes
HEAP = 0x58000000            # the game's allocations
IMAGE_BASE = 0x5F000000      # image handle = IMAGE_BASE + image id
TEXT_BASE = 0x71000000       # string handle = TEXT_BASE + string id
RETURN = 0x0E000000          # the startup emulation's halt page

GAMES = {
    "vv4": {
        "ctor": 0x419FA0, "draw": 0x41A5A0, "click": 0x41AD60,
        "screen": (800, 600), "singleton_global": 0x4CB51C,
        "new": 0x470C5C, "graphics": 0x408130, "images": 0x44CCF0,
        "image_calls": (0x44CD90, 0x44CB60, 0x44CB70), "state": 0x41FE70, "strings": 0x44DA20,
        "config": 0x402DE0, "tile_bounds": 0x40A990, "add_child": 0x40C190,
        "button": 0x401C20, "button_text": 0x401600, "checkbox": 0x40BF70, "set_checked": 0x40BB00,
        "get_string": 0x44D3D0, "image": 0x409960, "left": 0x409BD0, "centred": 0x409BE0,
        "tile": 0x409A00, "fullscreen_read": 0x408360, "set_speed": 0x41ACB0, "sound": 0x448E10,
        "toggle_query": 0x408350, "toggle_on": 0x409FB0, "toggle_off": 0x409FA0,
        "done_image": 0x82, "done_size": (158, 55),   # main_wide_button2.png, one of three frames
        "difficulty": 0x170F4, "speed": 0x17110, "fullscreen": 0x1711D,
    },
    "vv5": {
        "ctor": 0x41A800, "draw": 0x41ADF0, "click": 0x41B5C0,
        "screen": (1024, 768), "singleton_global": 0x4DACE0,
        "new": 0x47BBDC, "graphics": 0x4080C0, "images": 0x44FBB0,
        "image_calls": (0x44FC50, 0x44FA20, 0x44FA30), "state": 0x425950, "strings": 0x450D40,
        "config": 0x402D70, "tile_bounds": 0x40AE90, "add_child": 0x40C680,
        "button": 0x401BD0, "button_text": 0x4015D0, "checkbox": 0x40C460, "set_checked": 0x40BFF0,
        "get_string": 0x4506D0, "image": 0x409B90, "left": 0x409EA0, "centred": 0x409EB0,
        "tile": 0x409C30, "fullscreen_read": 0x408330, "set_speed": 0x41B500, "sound": 0x44C440,
        "toggle_query": 0x408320, "toggle_on": 0x40A280, "toggle_off": 0x40A270,
        "done_image": 0x75, "done_size": (140, 32),   # popup_button1.png, one of three frames
        "difficulty": 0x17D54, "speed": 0x17D7C, "fullscreen": 0x17D89,
    },
}
TILE = 64

# Fixed objects in REGION.
GRAPHICS = REGION + 0x0000          # [0] -> GRAPHICS_IMPL
GRAPHICS_IMPL = REGION + 0x0100     # +8 screen width, +0xC height, +0x5C default font
IMAGES = REGION + 0x0400
STRINGS = REGION + 0x0500
SINGLETON = REGION + 0x0600         # [0] -> FAKE_VTABLE
FAKE_VTABLE = REGION + 0x0700       # every slot: xor eax, eax; ret
FAKE_RET = REGION + 0x0800
BUTTON_VTABLE = REGION + 0x0900
BUTTON_CODE = REGION + 0x0A00
DIALOG = REGION + 0x1000
STATE = REGION + 0x100000


@dataclass
class Child:
    kind: str                   # "done" or "checkbox"
    ident: int
    x: int                      # as the game places it, from the dialog's frame
    y: int
    w: int
    h: int


@dataclass
class Frame:
    images: list = field(default_factory=list)      # (image id, x, y) on screen
    texts: list = field(default_factory=list)       # (kind, string id or None, text ptr, x, y, colour, font)
    tiles: list = field(default_factory=list)       # (tile index, x, y)


class OptionsDialog:
    def __init__(self, game: str, machine, fullscreen_row: bool = True):
        self.game = game
        self.g = g = GAMES[game]
        self.mu = mu = machine.mu
        self.heap = HEAP
        self.children: list[Child] = []
        self.speed_calls: list[int] = []
        self._frame = Frame()
        self._pending_button = None
        mu.mem_map(REGION, 0x200000)
        mu.mem_map(HEAP, 0x400000)
        width, height = g["screen"]
        mu.mem_write(GRAPHICS, struct.pack("<I", GRAPHICS_IMPL))
        mu.mem_write(GRAPHICS_IMPL + 8, struct.pack("<II", width, height))
        mu.mem_write(GRAPHICS_IMPL + 0x5C, struct.pack("<I", 0x7F0F0F00))
        mu.mem_write(SINGLETON, struct.pack("<I", FAKE_VTABLE))
        mu.mem_write(FAKE_RET, b"\x33\xC0\xC3")
        mu.mem_write(FAKE_VTABLE, struct.pack("<64I", *([FAKE_RET] * 64)))
        mu.mem_write(g["singleton_global"], struct.pack("<I", SINGLETON))
        # Button object methods: +4 setPosition(x, y), +0xC width, +0x10 height.
        bw, bh = g["done_size"]
        code = {
            0x00: b"\xC2\x08\x00",                                   # setPosition: recorded by hook
            0x10: b"\xB8" + struct.pack("<I", bw) + b"\xC3",
            0x20: b"\xB8" + struct.pack("<I", bh) + b"\xC3",
        }
        for offset, body in code.items():
            mu.mem_write(BUTTON_CODE + offset, body)
        vt = [FAKE_RET] * 32
        vt[1], vt[3], vt[4] = BUTTON_CODE, BUTTON_CODE + 0x10, BUTTON_CODE + 0x20
        mu.mem_write(BUTTON_VTABLE, struct.pack("<32I", *vt))
        self._returns(g["graphics"], GRAPHICS, 0)
        self._returns(g["images"], IMAGES, 0)
        self._returns(g["state"], STATE, 0)
        self._returns(g["strings"], STRINGS, 0)
        self._returns(g["config"], 0, None)                    # cdecl: the caller pops
        for call in g["image_calls"]:
            mu.mem_write(call, bytes.fromhex("8B44240405") + struct.pack("<I", IMAGE_BASE) + b"\xC2\x04\x00")
        mu.mem_write(g["get_string"], bytes.fromhex("8B44240405") + struct.pack("<I", TEXT_BASE) + b"\xC2\x04\x00")
        for address, pop in ((g["image"], 0xC), (g["left"], 0x14), (g["centred"], 0x14), (g["tile"], 0x14),
                             (g["set_speed"], 4), (g["sound"], 4), (g["add_child"], 4),
                             (g["button_text"], 0x14), (g["set_checked"], 4), (g["tile_bounds"], 0xC),
                             (g["button"], 0x18), (g["checkbox"], 0x20)):
            mu.mem_write(address, b"\xC2" + struct.pack("<H", pop))
        mu.mem_write(g["fullscreen_read"], b"\x30\xC0\xC3")
        mu.mem_write(g["toggle_query"], b"\x30\xC0\xC3")
        mu.mem_write(g["toggle_on"], b"\xC3")
        mu.mem_write(g["toggle_off"], b"\xC3")
        hooks = {
            g["new"]: self._new, g["image"]: self._image, g["left"]: lambda: self._text("left"),
            g["centred"]: lambda: self._text("centred"), g["tile"]: self._tile,
            g["set_speed"]: self._speed, g["tile_bounds"]: self._tile_bounds,
            g["button"]: self._button, g["checkbox"]: self._checkbox, BUTTON_CODE: self._button_place,
        }
        for address, fn in hooks.items():
            mu.hook_add(UC_HOOK_CODE, lambda uc, a, s, d, fn=fn: fn(), begin=address, end=address)
        self.fullscreen_row = fullscreen_row

    # -- leaves -------------------------------------------------------------
    def _returns(self, address, value, pop):
        body = b"\xB8" + struct.pack("<I", value) + (b"\xC3" if not pop else b"\xC2" + struct.pack("<H", pop))
        self.mu.mem_write(address, body)

    def _sp(self):
        return self.mu.reg_read(UC_X86_REG_ESP)

    def _args(self, count):
        return struct.unpack(f"<{count}i", self.mu.mem_read(self._sp() + 4, 4 * count))

    def _new(self):
        (size,) = self._args(1)
        block = self.heap
        self.heap += (size + 15) & ~15
        self.mu.mem_write(block, bytes(size))
        sp = self._sp()
        ret = struct.unpack("<I", self.mu.mem_read(sp, 4))[0]
        self.mu.reg_write(UC_X86_REG_EAX, block)
        self.mu.reg_write(UC_X86_REG_ESP, sp + 4)
        self.mu.reg_write(UC_X86_REG_EIP, ret)

    def _tile_bounds(self):
        _a, _b, rect = self._args(3)
        self.mu.mem_write(rect & 0xFFFFFFFF, struct.pack("<4i", 0, 0, TILE, TILE))

    def _button(self):
        obj = self.mu.reg_read(UC_X86_REG_ECX)
        ident, image = self._args(2)
        self.mu.mem_write(obj, struct.pack("<I", BUTTON_VTABLE))
        self.mu.reg_write(UC_X86_REG_EAX, obj)
        self._pending_button = (ident, image - IMAGE_BASE)

    def _button_place(self):
        x, y = self._args(2)
        w, h = self.g["done_size"]
        self.children.append(Child("done", self._pending_button[1], x, y, w, h))

    def _checkbox(self):
        obj = self.mu.reg_read(UC_X86_REG_ECX)
        ident, image, x, y = self._args(4)
        self.mu.reg_write(UC_X86_REG_EAX, obj)
        self.children.append(Child("checkbox", ident, x, y, 48, 32))   # CheckboxStrip.png: two 48 x 32 frames

    def _image(self):
        image, x, y = self._args(3)
        self._frame.images.append((image - IMAGE_BASE if image >= IMAGE_BASE else image, x, y))

    def _text(self, kind):
        text, x, y, colour, font = self._args(5)
        text &= 0xFFFFFFFF
        ident = text - TEXT_BASE if text >= TEXT_BASE else None
        self._frame.texts.append((kind, ident, text, x, y, colour & 0xFFFFFFFF, font))

    def _tile(self):
        _image, x, y, tile, _alpha = self._args(5)
        self._frame.tiles.append((tile, x, y))

    def _speed(self):
        (value,) = self._args(1)
        self.speed_calls.append(value)

    # -- running ------------------------------------------------------------
    def _call(self, address, args=(), this=DIALOG, count=5_000_000):
        sp = 0x0F000000 - 0x30000
        frame = struct.pack("<I", RETURN) + b"".join(struct.pack("<I", a & 0xFFFFFFFF) for a in args)
        self.mu.mem_write(sp, frame)
        self.mu.reg_write(UC_X86_REG_ESP, sp)
        self.mu.reg_write(UC_X86_REG_ECX, this)
        self.mu.emu_start(address, RETURN, count=count)

    def construct(self):
        """Run the game's constructor, as the menu does (label "Done", style 0)."""
        self.children.clear()
        self.mu.mem_write(DIALOG, bytes(0x200))
        self.mu.mem_write(STATE, bytes(0x20000))
        self._call(self.g["ctor"], (TEXT_BASE, 0))
        if not self.fullscreen_row:
            self.mu.mem_write(DIALOG + 0x60, b"\x00")
        return self

    def field(self, offset, fmt="<i"):
        return struct.unpack(fmt, self.mu.mem_read(DIALOG + offset, struct.calcsize(fmt)))[0]

    @property
    def rect(self):
        """The dialog widget's rectangle on the screen (left, top, right, bottom)."""
        return struct.unpack("<4i", self.mu.mem_read(DIALOG + 0x14, 16))

    @property
    def origin(self):
        """The origin every row is drawn and hit-tested from (+0x78, +0x80)."""
        return self.field(0x78), self.field(0x80)

    def draw(self) -> Frame:
        self._frame = Frame()
        left, top, _right, _bottom = self.rect
        frame_object = self.field(0x3C, "<I")
        vtable = struct.unpack("<I", self.mu.mem_read(frame_object, 4))[0]
        draw = struct.unpack("<I", self.mu.mem_read(vtable + 12, 4))[0]
        self._call(draw, (left, top, struct.unpack("<I", struct.pack("<f", 1.0))[0]), this=frame_object)
        self._call(self.g["draw"])
        return self._frame

    def set(self, difficulty=None, speed=None, fullscreen=None):
        if difficulty is not None:
            self.mu.mem_write(STATE + self.g["difficulty"], struct.pack("<i", difficulty))
        if speed is not None:
            self.mu.mem_write(STATE + self.g["speed"], struct.pack("<i", speed))
        if fullscreen is not None:
            self.mu.mem_write(STATE + self.g["fullscreen"], bytes([fullscreen]))
            self.mu.mem_write(DIALOG + 0xAD, bytes([fullscreen]))

    def get(self, name):
        if name == "fullscreen":
            return self.mu.mem_read(STATE + self.g["fullscreen"], 1)[0]
        return struct.unpack("<i", self.mu.mem_read(STATE + self.g[name], 4))[0]

    def press(self, x: int, y: int):
        """A mouse press at screen (x, y); returns the speed calls it made."""
        self.speed_calls.clear()
        self._call(self.g["click"], (2, x, y))
        return list(self.speed_calls)

    def frame_box(self, frame: Frame):
        xs = [x for _, x, _ in frame.tiles]
        ys = [y for _, _, y in frame.tiles]
        return min(xs), min(ys), max(xs) + TILE, max(ys) + TILE
