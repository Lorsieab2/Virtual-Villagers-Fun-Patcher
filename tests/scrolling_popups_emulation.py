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
# The companion's TEST build (the same source with VVFP_TEST: the exports below that read its state); the shipped
# DLL exports none of them.  It is loaded in the shipped DLL's place.
DLL_NAME = "VVFP Scrolling Popups.dll"
TEST_DLL = ROOT / "tests" / "test_dlls" / "VVFP Scrolling Popups.test.dll"

# Per game: the dialog constructor, its base constructor (this, fade flag), the base draw (panel + body), the body
# draw, the tail [start, the `mov byte [esi+0x4C], 1` it ends at), the frame slots of the image manager and the
# event, the panel picture's fetch arguments, the OK and choice button picture ids, the centred text draw, the
# panel's width, the text box (x, width) and the title's x, the ctx holder global, the image manager and its fetch,
# and the pump's mouse call site and its target.
GAMES = {
    "vv3": dict(ctor=0x4192F0, base=0x40E100, base_draw=None, body=0x418510, tail=0x41982B, frame_mgr=0x10,
                frame_event=0x54, ok_id=0x10, choice_id=0x04, centred=0x40A070, width=0x200, screen=(800, 600),
                holder=0x4B34A8, app=0x4B309C, mgr=0x42E9D0, lookup=0x42E6F0, get=0x42EA80, mouse=0x40451E, dispatch=0x4020A0, justify=0x40A0C0, draw_site=0x418591,
                size_site=0x41983F, sizer=0x40DDD0, single=0x4197D6, single_holder=0x1C, add_child=0x40C1F0,
                box_ctor=0x41C7A0, box_zeros=2, box_vtable=0x47F3AC, box_size_site=0x41C53F, box_sizer=0x40DDD0,
                ctl_site=0x40D807, text_draw=0x40A060, frame_draw=0x409F80,
                strings=(0x42F740, 0x42F190)),
    "vv4": dict(ctor=0x417790, base=0x40DD00, base_draw=None, body=0x416EC0, tail=0x417CD8, frame_mgr=0x14,
                frame_event=0x58, ok_id=0x82, choice_id=0x83, centred=0x409BE0, width=0x200, screen=(800, 600),
                holder=0x4CB928, app=0x4CB51C, mgr=0x44CCF0, lookup=0x44C8A0, get=0x44CB80, mouse=0x404B02, dispatch=0x402320, justify=0x409C30, draw_site=0x416F4C,
                size_site=0x417CEF, sizer=0x40DE20, single=0x417C83, single_holder=0x20, add_child=0x40C190,
                box_ctor=0x419F00, box_zeros=2, box_vtable=0x48D3C4, box_size_site=0x419BE0, box_sizer=0x40DE20,
                ctl_site=0x40CFC9, text_draw=0x409BD0, frame_draw=0x409A00,
                strings=(0x44DA20, 0x44D3D0)),
    "vv5": dict(ctor=0x418020, base=0x40E1F0, base_draw=None, body=0x417660, tail=0x41855F, frame_mgr=0x14,
                frame_event=0x58, ok_id=0x75, choice_id=0x65, centred=0x409EB0, width=0x2C0, screen=(1024, 768),
                holder=0x4DB0E8, app=0x4DACE0, mgr=0x44FBB0, lookup=0x44F760, get=0x44FA40, mouse=0x404A92, dispatch=0x4022D0, justify=0x409F00, draw_site=0x4176E9,
                size_site=0x418573, sizer=0x40E310, single=0x41850A, single_holder=0x20, add_child=0x40C680,
                box_ctor=0x41A760, box_zeros=2, box_vtable=0x4985D4, box_size_site=0x41A47B, box_sizer=0x40E310,
                ctl_site=0x40D4B9, text_draw=0x409EA0, frame_draw=0x409C30,
                strings=(0x450D40, 0x4506D0)),
    # A New Home and The Lost Children (no justified paragraph, no island-event dialog row here).
    "vv1": dict(screen=(800, 600), holder=0x48B2E8, app=0x48AEDC, mouse=0x403C6E, dispatch=0x401FE0,
                add_child=0x40AB80, centred=0x4094C0,
                box_ctor=0x4275B0, box_zeros=4, box_vtable=0x459AB0, box_size_site=0x427378, box_sizer=0x40C760,
                ctl_site=0x40C197, text_draw=0x4094B0, frame_draw=0x4093E0,
                strings=(0x433980, 0x433970), sound=(0x430BC0, 0x431450)),
    "vv2": dict(screen=(800, 600), holder=0x499BC8, app=0x4997BC, mouse=0x403EFE, dispatch=0x402070,
                add_child=0x40B560, centred=0x4096B0,
                box_ctor=0x433120, box_zeros=4, box_vtable=0x476DC4, box_size_site=0x432EE8, box_sizer=0x40D140,
                ctl_site=0x40CB77, text_draw=0x4096A0, frame_draw=0x4095D0,
                strings=(0x441690, 0x441680), sound=(0x43E460, 0x43EFF0)),
}
ASSETS = ROOT / "assets" / "scrolling_popups"
# The games' string tables (data/translations/vvN_strings.json): (first row, rows, stride, English pointer's offset).
STRING_TABLES = {"vv1": (4747784, 629, 20, 4), "vv2": (4809472, 876, 12, 4), "vv3": (4897168, 1210, 16, 8),
                 "vv4": (4997624, 1338, 16, 8), "vv5": (5059056, 1409, 16, 8)}
SPRINTF = {"vv3": 0x46EFCD, "vv4": 0x4716DB, "vv5": 0x47C046}
# The panels whose lines are text controls, by their constructors (no arguments): Create Nickname (all five),
# Statistics (A New Home, The Lost Children).
LABEL_PANELS = {"vv1": {"nickname": 0x415510, "statistics": 0x431B30},
                "vv2": {"nickname": 0x41AC90, "statistics": 0x43F860},
                "vv3": {"nickname": 0x41BA90, "roster": 0x41A110}, "vv4": {"nickname": 0x4190B0}, "vv5": {"nickname": 0x4197D0}}
# The tombstone (the grave's readout), per game.  A New Home and The Lost Children: its vtable, base constructor,
# sizer and its 9-slice picture (the strip constructor, the file), its OK button's field, its fields the body draw
# reads (the grave's slot, the grave manager, the string table) and the grave's fields in the manager (the name;
# the skill value, the job, the age), the place Cause of Death's hook draws its cause line from (the site, its
# stolen bytes, where it returns, the registers holding the panel, the renderer and the centre x; the centred draw,
# the font global).  The later three: the constructor (the game's own code makes it), whether it takes the Roster of
# the Dead entry's index (and where the entries live) or the entry itself, and the entry's fields.
TOMBS = {
    "vv1": dict(vt=0x481B58, base=0x40C9E0, sizer=0x40C760, strip=0x40A070, picture=b"GreenDlgTileGrid.png",
                button=0x88, slot=0x60, manager=0x74, strings=0x7C, manager_size=0x10000,
                name=lambda slot: (slot + 0x3B5) * 0x2C, value=0xA338, job=0xA33C, age=0xA340,
                cod=dict(site=0x436700, stolen=bytes.fromhex("5F5E5D5B81C4CC000000"), back=None, panel="ebx",
                         renderer="esi", x="ebp", draw=0x4094C0, font=0x48B608)),
    "vv2": dict(vt=0x48FB48, base=0x40D470, sizer=0x40D140, strip=0x40A270, picture=b"GreenDlgTileGrid.png",
                button=0x90, slot=0x60, manager=0x78, strings=0x80, manager_size=0x30000,
                name=lambda slot: slot * 0x7C + 0x2EB0C, value=0x2EB78, job=0x2EB7C, age=0x2EB80,
                epitaph=0x84, flag=0x64,
                cod=dict(site=0x444790, stolen=bytes.fromhex("8B8D84000000"), back=0x444796, panel="ebp",
                         renderer="esi", x="ebx", draw=0x4096B0, font=0x499F18)),
    "vv3": dict(vt=0x47F498, ctor=0x41E6D0, by_index=True, entries=0x5973F0 + 0x974, entry_size=0x30,
                age=0x1C, job=0x20, value=0x24, cause=0x2C),
    "vv4": dict(vt=0x48D4EC, ctor=0x41BBA0, by_index=False, entry_size=0x5C, age=0x1C, job=0x28, value=0x2C,
                cause=0x34),
    "vv5": dict(vt=0x4986E8, ctor=0x41C3F0, by_index=False, entry_size=0x5C, age=0x1C, job=0x28, value=0x2C,
                cause=0x34),
}
# A New Home's and The Lost Children's island-event dialogs (plain; two choices; crate / sacks and vials): the
# vtable, base constructor, the size site (its `push ebp` (the height) and two more pushes start 5 bytes before it,
# then `mov ecx, esi`) and the registers holding the width and the panel picture there, the width, the room the
# constructor adds below the text (5/2 or 4 x a button's height), the text fields (a; b when the byte at flag is set),
# the text manager (whose +4 is the holder), and the y the constructor keeps.
EVENTS = {
    "vv1": {
        "plain": dict(vt=0x459AE4, base=0x40C9E0, size=0x428830, regs=("edx", "eax"), width=0x1D0, room=(5, 2),
                      a=0x277F, b=0, flag=0, mgr=0x50AC, y=0x6C, end=0x42884C),
        "choice": dict(vt=0x459578, base=0x40C9E0, size=0x41A634, regs=("ecx", "edx"), width=0x1C2, room=(4, 1),
                       a=0x74, b=0x2783, flag=0x50, mgr=0x50AC, y=0x64, end=0x41A650),
        "crate": dict(vt=0x459BF8, base=0x40C9E0, size=0x42D2B4, regs=("ecx", "edx"), width=0x1C2, room=(4, 1),
                      a=0x74, b=0x2783, flag=0x50, mgr=0x50B0, y=0x6C, end=0x42D2D0),
    },
    "vv2": {
        "plain": dict(vt=0x476DF8, base=0x40D470, size=0x434A6B, regs=("edx", "eax"), width=0x1D0, room=(5, 2),
                      a=0x277F, b=0, flag=0, mgr=0x50AC, y=0x6C, end=0x434A87),
        "choice": dict(vt=0x476714, base=0x40D470, size=0x42255F, regs=("ecx", "edx"), width=0x1C2, room=(4, 1),
                       a=0x7C, b=0x278B, flag=0x50, mgr=0x50B4, y=0x64, end=0x42257B),
        "crate": dict(vt=0x476F30, base=0x40D470, size=0x439FA4, regs=("ecx", "edx"), width=0x1C2, room=(4, 1),
                      a=0x74, b=0x2783, flag=0x50, mgr=0x50B0, y=0x6C, end=0x439FC0),
    },
}
EVENT_HEIGHT = {"vv1": 0x402100, "vv2": 0x402190}
EVENT_STRIP = {"vv1": 0x40A070, "vv2": 0x40A270}
TIP_ID = 0x106                    # the string id a tip is made with here (its text: Dialog.tip_text)
# The tip (theTipDialog), per game: its constructor and its arguments (the string id, or the text for The Secret
# City's, and zeros: not a tutorial tip), its body draw.
TIPS = {
    "vv1": dict(size_site=0x436006, ctor=0x435EB0, args=lambda text_va: (TIP_ID, 0, 0, 0)),
    "vv2": dict(size_site=0x443D86, ctor=0x443B90, args=lambda text_va: (TIP_ID, 0, 0, 0, 0)),
    "vv3": dict(size_site=0x41DFF1, ctor=0x41E5E0, args=lambda text_va: (text_va,)),
    "vv4": dict(size_site=0x41B4B9, ctor=0x41BAB0, args=lambda text_va: (TIP_ID, 0, 0, 0, 0)),
    "vv5": dict(size_site=0x41BD13, ctor=0x41C300, args=lambda text_va: (TIP_ID, 0, 0, 0, 0)),
}   # the pictures A New Home and The Lost Children borrow


def _map_rgba(mc, arg, ret):
    """SDL_MapRGBA(format, r, g, b, a): the colour in the format's masks."""
    fmt = arg(0)
    masks = struct.unpack("<4I", mc.mu.mem_read(fmt + 0x0C, 16))
    shifts = bytes(mc.mu.mem_read(fmt + 0x20, 4))
    value = 0
    for k, c in enumerate((arg(1) & 0xFF, arg(2) & 0xFF, arg(3) & 0xFF, arg(4) & 0xFF)):
        value |= (c << shifts[k]) & masks[k]
    ret(value)


def _map_rgb(mc, arg, ret):
    """SDL_MapRGB(format, r, g, b): the colour in the format's masks, opaque."""
    _map_rgba(mc, lambda k: arg(k) if k < 4 else 255, ret)


def _tables() -> dict:
    return json.loads((ROOT / "data" / "font_glyph_tables.json").read_text(encoding="utf-8"))


class Dialog:
    """One published build of `game` with the island-event dialog to make, draw and click."""

    def __init__(self, game: str, selection=None, font: str = "ldwarialbold") -> None:
        self.game = game
        self.g = dict(GAMES[game])
        self.watch = None
        se.EXTRA_IMPORTS.setdefault("SDL_MapRGBA", (0, _map_rgba))
        se.EXTRA_IMPORTS.setdefault("SDL_MapRGB", (0, _map_rgb))
        # An editable text box's background (the later three's tombstone epitaph): not drawn here.
        se.EXTRA_IMPORTS.setdefault("SDL_FillRect", (0, lambda mc, arg, ret: ret(0)))
        self.run = ute.FontRun(game, "collection_progression",
                               tuple(selection) if selection else (f"{game}_scrolling_popups",), _tables(),
                               swap={DLL_NAME: TEST_DLL})
        self.run.r.clip = None            # the game's own clip test, not FontRun's always-on-screen answer
        # Every picture the game's loader loads, by file name (the companion builds its own strips of the scrollbar
        # pictures from the game's files, so each of those names may be loaded more than once).
        self.loaded: dict[str, set] = {}
        load = self.run._picture

        def _picture(path: str) -> int:
            name = path.replace("/", "\\").split("\\")[-1]
            surface = self._shipped_picture(name) if name.lower().startswith("vvfp_scroll_") else load(path)
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
        # The game's text manager (its getter loads the string file through the game object, which the emulation
        # has not got): answered with a stand-in whose first fields are the font, and every string it is asked for
        # by id is "OK" (the buttons' labels).
        getter, lookup = self.g["strings"]
        self.texts = None
        self.english = False              # True: every string id looked up is the game's own English text
        self.string_overrides: dict = {}  # string id -> text (a translation, say)
        self.real_children = False        # True: the game's own add-child runs as well (its window list)
        self.tip_text = None              # the text the game's string table gives for TIP_ID (a tip's text)
        self.looked_up: list[int] = []
        self.mu.hook_add(UC_HOOK_CODE, self._strings, begin=getter, end=getter, user_data=0)
        self.mu.hook_add(UC_HOOK_CODE, self._strings, begin=lookup, end=lookup, user_data=4)
        # A New Home's and The Lost Children's message box fetches its button's click sound from the sound manager
        # (whose getter loads the sounds through the game object): no sound here.
        if "sound" in self.g:
            getter, fetch = self.g["sound"]
            self.mu.hook_add(UC_HOOK_CODE, self._no_sound, begin=getter, end=getter, user_data=0)
            self.mu.hook_add(UC_HOOK_CODE, self._no_sound, begin=fetch, end=fetch, user_data=4)
        # The C runtime's sprintf (the later three's tombstone constructor prints its lines with it; its locale
        # needs the runtime's per-thread data, which the emulation has not got): answered from Python.
        if game in SPRINTF:
            self.mu.hook_add(UC_HOOK_CODE, self._sprintf, begin=SPRINTF[game], end=SPRINTF[game])
        self.passed: list[tuple[int, int, int]] = []    # mouse events the game's dispatcher received
        self.mu.hook_add(UC_HOOK_CODE, self._add_child, begin=self.g["add_child"], end=self.g["add_child"])
        self.children: list[int] = []     # what the dialogs made add to their window, in order
        for site in (self.g.get("size_site"), self.g["box_size_site"], TIPS[game]["size_site"],
                     *(e["size"] for e in EVENTS.get(game, {}).values())):
            if site:
                self.mu.hook_add(UC_HOOK_CODE, self._at_size_site, begin=site, end=site)
        for sizer in sorted({self.g.get("sizer"), self.g["box_sizer"]} - {None}):
            self.mu.hook_add(UC_HOOK_CODE, self._at_size, begin=sizer, end=sizer)
        self.size_requests: list[int] = []
        self.stock_heights: list[int] = []
        self.width_requests: list[int] = []
        self.stock_widths: list[int] = []
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
        self.manager = self.run._call(self.g["mgr"], 0) if "mgr" in self.g else None
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
            if name == "GetSystemTimeAsFileTime":
                mu.mem_write(arg(0), b"\0" * 8)               # a tip's timer start: time 0
                ret(0, 4)
                return
            if name == "SDL_GetTicks":            # a tombstone's text box notes the time it was made
                ret(0, 0)
                return
            if name.startswith("_FSOUND_") and "@" in name:
                ret(0, int(name.rsplit("@", 1)[1]))      # no sound here (a message box's sound manager)
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

    def _no_sound(self, mu, address, size, pop):
        sp = mu.reg_read(UC_X86_REG_ESP)
        to = struct.unpack("<I", mu.mem_read(sp, 4))[0]
        mu.reg_write(UC_X86_REG_EAX, self.m.font_heap.alloc(0x700) if pop == 0 else 0)
        mu.reg_write(UC_X86_REG_ESP, sp + 4 + pop)
        mu.reg_write(UC_X86_REG_EIP, to)

    def _strings(self, mu, address, size, pop):
        sp = mu.reg_read(UC_X86_REG_ESP)
        to = struct.unpack("<I", mu.mem_read(sp, 4))[0]
        if pop == 0:
            if self.texts is None:
                self.texts = self.m.font_heap.alloc(0x40)
                mu.mem_write(self.texts, struct.pack("<II", self.font, self.font))
            value = self.texts
        else:
            wanted = struct.unpack("<I", mu.mem_read(sp + 4, 4))[0]
            self.looked_up.append(wanted)
            if wanted in self.string_overrides:
                value = self._cstr(self.string_overrides[wanted])
            elif self.english:
                value = self._english_va(wanted)
            else:
                value = self._cstr(self.tip_text if wanted == TIP_ID and self.tip_text is not None else b"OK")
        mu.reg_write(UC_X86_REG_EAX, value)
        mu.reg_write(UC_X86_REG_ESP, sp + 4 + pop)
        mu.reg_write(UC_X86_REG_EIP, to)

    def _sprintf(self, mu, address, size, user):
        """sprintf(out, format, ...) (cdecl): %s, %d, %i, %u and %% as the C runtime prints them."""
        sp = mu.reg_read(UC_X86_REG_ESP)
        to, out, fmt = struct.unpack("<III", mu.mem_read(sp, 12))
        text = bytes(mu.mem_read(fmt, 512)).split(b"\0")[0]
        result, k, arg = b"", 0, sp + 12
        while k < len(text):
            c = text[k:k + 1]
            if c == b"%" and k + 1 < len(text):
                spec = text[k + 1:k + 2]
                k += 2
                if spec == b"%":
                    result += b"%"
                    continue
                value = self.u32(arg)
                arg += 4
                if spec == b"s":
                    result += bytes(mu.mem_read(value, 1024)).split(b"\0")[0] if value else b"(null)"
                elif spec in (b"d", b"i"):
                    result += str(struct.unpack("<i", struct.pack("<I", value))[0]).encode()
                elif spec == b"u":
                    result += str(value).encode()
                else:
                    raise AssertionError(f"sprintf %{spec!r}")
                continue
            result += c
            k += 1
        mu.mem_write(out, result + b"\0")
        mu.reg_write(UC_X86_REG_EAX, len(result))
        mu.reg_write(UC_X86_REG_ESP, sp + 4)
        mu.reg_write(UC_X86_REG_EIP, to)

    def _add_child(self, mu, address, size, user):
        """The window's add-child (thiscall(window; child) ret 4): kept here, in order (the stand-in buttons need no
        window list; a message box's text and buttons are drawn from it).  With `real_children` the game's own
        add-child runs too (the window's list, which the companion walks for a tombstone's lines)."""
        sp = mu.reg_read(UC_X86_REG_ESP)
        to, child = struct.unpack("<II", mu.mem_read(sp, 8))
        self.children.append(child)
        if self.real_children:
            return
        mu.reg_write(UC_X86_REG_ESP, sp + 8)
        mu.reg_write(UC_X86_REG_EIP, to)

    def _at_size_site(self, mu, address, size, user):
        """The constructor's panel height as it makes the sizer call (the stock formula's result), and width."""
        sp = mu.reg_read(UC_X86_REG_ESP)
        self.stock_heights.append(struct.unpack("<i", mu.mem_read(sp + 8, 4))[0])
        self.stock_widths.append(struct.unpack("<i", mu.mem_read(sp + 4, 4))[0])

    def _at_size(self, mu, address, size, user):
        """The height the sizer is given (after the companion, when it caps it), and the width."""
        sp = mu.reg_read(UC_X86_REG_ESP)
        self.size_requests.append(struct.unpack("<i", mu.mem_read(sp + 12, 4))[0])
        self.width_requests.append(struct.unpack("<i", mu.mem_read(sp + 8, 4))[0])

    def _shipped_picture(self, name: str) -> int:
        """A picture shipped with the companion (assets/scrolling_popups), as the game's loader loads one."""
        from vv_picture_image import decode_png
        img = decode_png((ASSETS / name).read_bytes())
        raw = bytearray()
        d = img.data
        for i in range(0, len(d), 4):
            raw += struct.pack("<I", (d[i + 3] << 24) | (d[i] << 16) | (d[i + 1] << 8) | d[i + 2])
        return self.run._new_surface(img.width, img.height, 0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000,
                                     bytes(raw))

    def _object(self, methods: dict[int, tuple]) -> int:
        """An object whose vtable slot (byte offset) -> (fn, pop[, wants this])."""
        heap = self.m.font_heap
        vtable = heap.alloc(0x80)
        for slot, spec in methods.items():
            self.mu.mem_write(vtable + slot, struct.pack("<I", self._method(*spec)))
        obj = heap.alloc(0x40)
        self.mu.mem_write(obj, struct.pack("<I", vtable))
        return obj

    def _english_va(self, wanted: int) -> int:
        """The game's own English text for string id `wanted` (its string table in the executable)."""
        va, count, stride, eng = STRING_TABLES[self.game]
        for k in range(count):
            row = va + k * stride
            if self.u32(row) == wanted:
                return self.u32(row + eng)
        return self._cstr(b"?")

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

    def justify_height_widened(self, text_va: int, width: int) -> int:
        """The stock paragraph's height of a text that may hold a word wider than `width` (on which the stock
        paragraph never finishes): measured at a width wide enough for its widest word, as the constructor's own
        measures are when the companion widens them (the harness stands in for the two-choice tail's start)."""
        for _ in range(6):
            try:
                return self.run._call(self.g["justify"], self.holder, text_va, 0, 0, width, self.colour, self.font,
                                      1, count=5_000_000)
            except Exception:
                width *= 2
        raise AssertionError("the paragraph never finished")

    def companion_export(self, name: str) -> int:
        dll = next(m for k, m in self.m.modules.items() if "scrolling" in k)
        return self.run._call(dll.exports[name], 0)

    VIEW = ("shown", "box_x", "box_y", "box_w", "box_h", "content_w", "content_h", "vbar", "hbar", "vx", "vy", "vh",
            "arrow_h", "hx", "hy", "hw", "hh", "line", "sx", "sy")

    def view(self) -> dict:
        """The companion's view of the dialog it drew last (VvfpScrollingPopupsTestView, the test build)."""
        dll = next(m for k, m in self.m.modules.items() if "scrolling" in k)
        out = self.m.font_heap.alloc(4 * len(self.VIEW))
        n = self.run._call(dll.exports["VvfpScrollingPopupsTestView"], 0, out, len(self.VIEW))
        values = struct.unpack("<%di" % n, self.mu.mem_read(out, 4 * n))
        return dict(zip(self.VIEW, values))

    def scroll(self) -> tuple[int, int]:
        v = self.view()
        return v["sx"], v["sy"]

    ART_FILES = {"up": "uparrowbutton.png", "down": "downarrowbutton.png", "track": "verticalscrolltrack.png",
                 "knob": "verticalscrollknob.png", "wide": "wideslider2.png", "handle": "sliderhandle.png"}

    def art_surfaces_by_name(self) -> dict:
        """The scrollbar pictures' SDL surfaces, by name: every surface the game's loader made from that file."""
        return {name: self.loaded.get(file, set()) | self.loaded.get(f"vvfp_scroll_{name}.png", set())
                for name, file in self.ART_FILES.items()}

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
            self.text_height = max(self.justify_height_widened(self.text_va, box_w), line)
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

    # -- the message box ----------------------------------------------------------------------------------------------
    def make_box(self, text: bytes) -> int:
        """A message box with `text` (OK alone), made by the game's own constructor (the one taking a string): its
        text control, its button, the sizer call and the placing of both, all the game's code."""
        g = self.g
        self.children = []
        self.dialog = d = self.m.font_heap.alloc(0x200)
        self.box_text = self._cstr(text)
        self.size_requests, self.stock_heights, self.width_requests, self.stock_widths = [], [], [], []
        self.run._call(g["box_ctor"], d, self.box_text, *([0] * g["box_zeros"]))
        self.put(d + 0x44, 0x3F800000)    # its opening fade (+0x44, 0 to 1.0) at its end, as the game shows it
        for child in self.children:       # shown, as its modal loop shows it: each control's show (vtable+0x14)
            self.run._call(self.u32(self.u32(child) + 0x14), child, 1)
        self.stock_height = self.stock_heights[-1] if self.stock_heights else None
        self.stock_width = self.stock_widths[-1] if self.stock_widths else None
        return d

    def make_event(self, kind: str, text: bytes, result: bytes | None = None, button_h: int = 30) -> int:
        """A New Home's / The Lost Children's island-event dialog `kind` with `text` (and a result text, shown when
        `show_result` is called): the base constructor, the dialog's own vtable and fields, then the constructor's
        own size site run with the height its own formula gives (the text's height by the game's routine plus the
        room for its buttons), through the y it keeps."""
        e = EVENTS[self.game][kind]
        heap = self.m.font_heap
        self.children = []
        self.event_kind = e
        self.dialog = d = heap.alloc(0x5200)
        self.run._call(e["base"], d, 0)
        self.put(d, e["vt"])
        self.mu.mem_write(d + e["a"], text[:9999] + b"\0")
        if e["b"]:
            self.mu.mem_write(d + e["b"], (result or b"")[:9999] + b"\0")
            self.mu.mem_write(d + e["flag"], b"\0")
        if self.texts is None:
            self.texts = heap.alloc(0x40)
            self.mu.mem_write(self.texts, struct.pack("<II", self.font, self.font))
        self.put(d + e["mgr"], self.texts)
        self.put(d + e["mgr"] + 4, self.holder)
        for field in (0x5098, 0x50A0):        # no villager's picture beside the text
            self.put(d + field, -1)
        strip = heap.alloc(0x40)
        self.run._call(EVENT_STRIP[self.game], strip, self._cstr(b"OrangeDlgTileGrid.png"), 9, 1)
        height = self.run._call(EVENT_HEIGHT[self.game], self.font, d + e["a"])
        num, den = e["room"]
        h = height + (num * button_h) // den + 0x23
        mu = self.mu
        frame = FRAME
        mu.mem_write(frame, b"\0" * 0x100)
        regs = {"eax": UC_X86_REG_EAX, "ecx": UC_X86_REG_ECX, "edx": UC_X86_REG_EDX}
        for reg, value in ((UC_X86_REG_ESP, frame), (UC_X86_REG_ESI, d), (UC_X86_REG_EBP, h),
                           (regs[e["regs"][0]], e["width"]), (regs[e["regs"][1]], strip)):
            mu.reg_write(reg, value)
        self.size_requests, self.stock_heights, self.width_requests, self.stock_widths = [], [], [], []
        self.m.stop_at = e["end"]
        self.m.error = None
        mu.emu_start(e["size"] - 5, e["end"], count=5_000_000)
        if self.m.error or mu.reg_read(UC_X86_REG_EIP) != e["end"]:
            raise AssertionError(self.m.error or f"event stopped at {mu.reg_read(UC_X86_REG_EIP):#x}")
        self.stock_height = self.stock_heights[-1] if self.stock_heights else None
        self.put(d + 0x44, 0x3F800000)
        return d

    def show_result(self) -> None:
        """The choice made: the result replaces the question (the flag the body draw reads), no re-size."""
        self.mu.mem_write(self.dialog + self.event_kind["flag"], b"\x01")

    def make_tip(self, text: bytes) -> int:
        """A tip with `text`, made by the game's own constructor (its OK button, its sizer call, its layout)."""
        t = TIPS[self.game]
        self.children = []
        self.tip_text = text
        self.looked_up = []
        self.dialog = d = self.m.font_heap.alloc(0x200)
        text_va = self._cstr(text)
        self.size_requests, self.stock_heights, self.width_requests, self.stock_widths = [], [], [], []
        self.run._call(t["ctor"], d, *t["args"](text_va))
        self.stock_height = self.stock_heights[-1] if self.stock_heights else None
        self.stock_width = self.stock_widths[-1] if self.stock_widths else None
        self.put(d + 0x44, 0x3F800000)    # its opening fade at its end
        for child in self.children:
            self.run._call(self.u32(self.u32(child) + 0x14), child, 1)
        return d

    # -- the tombstone --------------------------------------------------------------------------------------------
    def make_tomb(self, name: bytes, cause: bytes | None = None, job: int = 1, value: int = 60, age: int = 300,
                  cause_id: int = 1) -> int:
        """A tombstone for a grave of `name`, with the game's own English texts.  A New Home and The Lost Children:
        the dialog's base constructor, vtable, the fields its body draw reads, its picture sized by the game's own
        sizer (320 x 320, as its constructor asks), an OK button (a stand-in, 30 px high) and, when `cause` is given,
        Cause of Death's cause line (its hook in the body draw replayed: _cod_line).  The later three: the game's own
        constructor on a Roster of the Dead entry for `name` (its labels, its Done button, the window's list); the
        cause line is the game's own (`cause_id`)."""
        t = TOMBS[self.game]
        heap = self.m.font_heap
        mu = self.mu
        self.children = []
        self.english = True
        if "ctor" in t:
            if t["by_index"]:
                entry = t["entries"]              # slot 0 of the Roster of the Dead
                arg = heap.alloc(8)
                self.put(arg, 0)
            else:
                entry = arg = heap.alloc(0x100)
            mu.mem_write(entry, b"\0" * t["entry_size"])
            mu.mem_write(entry, name[:0x1B] + b"\0")
            self.put(entry + t["age"], age)
            self.put(entry + t["job"], job)
            self.put(entry + t["value"], value)
            self.put(entry + t["cause"], cause_id)
            self.dialog = d = heap.alloc(0x200)
            self.size_requests, self.stock_heights, self.width_requests, self.stock_widths = [], [], [], []
            self.real_children = True
            try:
                # The Secret City's takes (the picture kind, the entry's index); the later two (the entry, the kind).
                self.run._call(t["ctor"], d, *((1, arg) if t["by_index"] else (arg, 1)))
            finally:
                self.real_children = False
            self.put(d + 0x44, 0x3F800000)
            for child in self.children:
                self.run._call(self.u32(self.u32(child) + 0x14), child, 1)
            return d
        self.dialog = d = heap.alloc(0x200)
        self.run._call(t["base"], d, 0)
        self.put(d, t["vt"])
        manager = heap.alloc(t["manager_size"])
        mu.mem_write(manager + t["name"](0), name[:0x2B] + b"\0")
        self.put(manager + t["value"], value)
        self.put(manager + t["job"], job)
        self.put(manager + t["age"], age)
        self.put(d + t["slot"], 0)
        self.put(d + t["manager"], manager)
        self.put(d + t["strings"], heap.alloc(0x40))
        if "epitaph" in t:
            self.put(d + t["epitaph"], self._object({0x0C: (lambda a: 0, 0)}))
            mu.mem_write(d + t["flag"], b"\0")
        self.tomb_button = self._object({0x0C: (lambda a: 120, 0), 0x10: (lambda a: 30, 0)})
        self.put(d + t["button"], self.tomb_button)
        strip = heap.alloc(0x40)
        self.run._call(t["strip"], strip, self._cstr(t["picture"]), 9, 1)
        self.run._call(t["sizer"], d, strip, 0x140, 0x140)
        self.put(d + 0x44, 0x3F800000)
        self._cod_line(cause)
        return d

    def _cod_line(self, cause: bytes | None) -> None:
        """Cause of Death's tombstone hook (A New Home, The Lost Children), replayed: at its site in the body draw a
        jump to code that makes the hook's own call -- the centred draw of the cause at the panel's centre x, 0xD7
        below the panel's top, in the game's font (native/vvfp_cause_of_death/cod_vv12.inc cod_grave_lines) -- then
        the stolen instructions, as that companion's detour does.  None: the site as the game has it."""
        c = TOMBS[self.game]["cod"]
        mu = self.mu
        if not hasattr(self, "_cod_saved"):
            self._cod_saved = bytes(mu.mem_read(c["site"], len(c["stolen"])))
        if cause is None:
            mu.mem_write(c["site"], self._cod_saved)
            return
        if not hasattr(self, "_cod_text"):
            self._cod_text = self.m.font_heap.alloc(0x400)   # one buffer: the code below is written once
        text = self._cod_text
        mu.mem_write(text, cause[:0x3FF] + b"\0")
        at = CODE + 0xF000
        reg = {"ebx": 3, "ebp": 5, "esi": 6}
        code = bytes([0x8B, 0x40 | reg[c["panel"]], 0x18])                 # mov eax, [panel + 0x18]
        code += b"\x05" + struct.pack("<I", 0xD7)                          # add eax, 0xD7
        code += b"\x6A\x00" + b"\xFF\x35" + struct.pack("<I", c["font"])     # push 0; push [font]
        code += b"\x50" + bytes([0x50 | reg[c["x"]]])                       # push eax; push x
        code += b"\x68" + struct.pack("<I", text)                          # push the cause
        code += bytes([0x8B, 0xC8 | reg[c["renderer"]]])                    # mov ecx, renderer
        code += b"\xE8" + struct.pack("<i", c["draw"] - (at + len(code) + 5))
        code += c["stolen"]
        if c["back"] is None:
            code += b"\xC3"
        else:
            code += b"\xE9" + struct.pack("<i", c["back"] - (at + len(code) + 5))
        mu.mem_write(at, code)
        jump = b"\xE9" + struct.pack("<i", at - (c["site"] + 5))
        mu.mem_write(c["site"], jump + b"\x90" * (len(c["stolen"]) - 5))

    def make_panel(self, kind: str, size: int = 0x400) -> int:
        """A panel of LABEL_PANELS made by the game's own constructor (no arguments), with the game's own English texts
        (and string_overrides): its labels, text box and buttons, the window's list."""
        ctor = LABEL_PANELS[self.game][kind]
        self.children = []
        self.english = True
        self.dialog = d = self.m.font_heap.alloc(size)
        self.size_requests, self.stock_heights, self.width_requests, self.stock_widths = [], [], [], []
        self.looked_up = []
        self.real_children = True
        try:
            self.run._call(ctor, d)
        finally:
            self.real_children = False
        self.put(d + 0x44, 0x3F800000)
        for child in self.children:
            self.run._call(self.u32(self.u32(child) + 0x14), child, 1)
        return d

    def control(self) -> int:
        """The message box's text control (the label wrapper's +0x10)."""
        return self.u32(self.children[0] + 0x10)

    def control_rect(self) -> tuple[int, int, int, int]:
        return struct.unpack("<4i", self.mu.mem_read(self.control() + 8, 16))

    def child_rect(self, child: int) -> tuple[int, int, int, int]:
        """A child's rectangle as its vtable+8 gives it (relative to the panel)."""
        out = self.m.font_heap.alloc(16)
        self.run._call(self.u32(self.u32(child) + 8), child, out)
        return struct.unpack("<4i", self.mu.mem_read(out, 16))

    def draw_box(self) -> list:
        """The message box as the game draws it: its panel (vtable+0x18), then each child (its vtable+0x18), in the
        order the window keeps them."""
        self.m.blits = []
        self.run._call(self.u32(self.u32(self.dialog) + 0x18), self.dialog)
        for child in self.children:
            self.run._call(self.u32(self.u32(child) + 0x18), child)
        return list(self.m.blits)

    def font_surfaces(self) -> set:
        """Every surface made from a font's picture (the glyphs' sources)."""
        return set().union(*(s for name, s in self.loaded.items() if name.startswith("ldw")))

    def text_blits(self, blits) -> list:
        """The blits of text: glyphs (not the panel's picture, the scrollbar art or a button's picture)."""
        fonts = self.font_surfaces()
        return [b for b in blits if b[0] in fonts]

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

    def wheel(self, notches: int, sideways: int = 0) -> None:
        """SDL_MOUSEWHEEL through the watch the companion registered (y = notches, + is away from the player;
        x = sideways, a tilt wheel's or touchpad's notches, + to the right)."""
        if self.watch is None:
            raise AssertionError("no event watch registered")
        event = self.m.font_heap.alloc(0x40)
        self.mu.mem_write(event, struct.pack("<IIIIii", 0x403, 0, 1, 0, sideways, notches))
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
