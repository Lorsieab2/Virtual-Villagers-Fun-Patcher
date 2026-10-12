"""The Villager Details name box is written back only to the villager it was
filled for -- all five games (Fix Vanilla Bugs).

Every game's Details screen fills its name box with the selected villager's
name and, on Done or an arrow, copies the box back into the villager the
selection names at that moment.  Nothing in the base games ties the two
together: if the selected record stopped holding the villager the box was
filled for -- the selection moved without a refill, or the record was reused
by another villager -- the box's name went into the wrong villager.

The fix: the screen object grows by a few bytes and remembers, at every fill,
the name pointer it filled from and a fingerprint of that villager (the
name's first two dwords XORed, the low byte also XORed with the sex byte).
Every write-back goes ahead only when its destination is that same name and
the villager there still has that fingerprint; otherwise nothing is written
(A New Home and The Lost Children skip getText; The Secret City, The Tree of
Life and New Believers hand the write-back the screen's own scratch name, so
the base game's copy and Show Full Names' direct getText both land there).
A New Home keeps its reload-flag guard (0x44A6F2) in front.

These tests run the real Details code of each rendered executable in unicorn
-- stock, fixed, with and without Show Full Names, in all three modes -- and
the protections fail on the stock bytes.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EIP, UC_X86_REG_ESP

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from vv_fun_patcher import load_builds, render_patched_bytes  # noqa: E402
from test_details_name_box import DetailsScreen, DONE_ID, NEXT_ID, NAME, STRIDE  # noqa: E402

STOCK_DIR = ROOT / "research" / "stock-executables"
EXES = {
    "vv1": "Virtual Villagers - A New Home.exe",
    "vv2": "Virtual Villagers - The Lost Children.exe",
    "vv3": "Virtual Villagers - The Secret City.exe",
    "vv4": "Virtual Villagers - The Tree of Life.exe",
    "vv5": "Virtual Villagers - New Believers.exe",
}
MODES = ("stock", "collection_progression", "immediate_fixed")


# The rows the identity guard adds to each game's Fix Vanilla Bugs, in catalog
# order: (file offset, stock bytes, patched bytes).  A New Home also changes two
# rows it already had (the refresh's strcpy call 0x4A66A and the 0x44A6F2 gap),
# pinned in tests/test_vv1_fix_vanilla_bugs.py.
NAME_IDENTITY_FIXES = {
    "vv1": (
        (0x1B756, "CC000000",
         "D4000000"),
        (0x1261, "909090909090909090909090909090",
         "8B4424088986CC000000E9C1080000"),
        (0x1B31, "90909090909090909090909090",
         "8B103350043250E0E913040000"),
        (0x1F51, "9090909090909090909090",
         "8996D0000000E924D40400"),
        (0x81E1, "909090909090909090909090909090",
         "8B4424043B86CC000000E9A1070000"),
        (0x8991, "90909090909090909090909090",
         "0F85661D04008B10E943010000"),
        (0x8AE1, "9090909090909090909090",
         "3350043250E0E9350C0000"),
        (0x9721, "9090909090909090909090",
         "3B96D0000000E9F5080000"),
        (0xA021, "9090909090909090909090",
         "0F85D6060400E9441B0000"),
    ),
    "vv2": (
        (0x24206, "4C050000",
         "54050000"),
        (0x1281, "909090909090909090909090909090",
         "8B44240489864C050000E9C1080000"),
        (0x1B51, "90909090909090909090909090",
         "8B103350043250D4E983040000"),
        (0x1FE1, "9090909090909090909090",
         "899650050000E924A50000"),
        (0x8471, "909090909090909090909090909090",
         "8B4424043B864C050000E911070000"),
        (0x8B91, "90909090909090909090909090",
         "0F85B50E00008B10E943010000"),
        (0x8CE1, "9090909090909090909090",
         "3350043250D4E9250C0000"),
        (0x9911, "9090909090909090909090",
         "3B9650050000E925010000"),
        (0x9A41, "9090909090909090909090909090",
         "0F8505000000E9042B0000C20800"),
        (0x663A6, "E86561FAFF",
         "E8D6AEF9FF"),
        (0x67945, "E8C64BFAFF",
         "E83799F9FF"),
        (0x67767, "E8E44DFAFF",
         "E8050DFAFF"),
        (0x677F8, "E8534DFAFF",
         "E8740CFAFF"),
        (0x678C6, "E8854CFAFF",
         "E8A60BFAFF"),
    ),
    "vv3": (
        (0x27A39, "3C030000",
         "64030000"),
        (0x20571, "909090909090909090909090909090",
         "8B44240489863C030000E921000000"),
        (0x205A1, "90909090909090909090909090",
         "8B103350043250F4E923000000"),
        (0x205D1, "9090909090909090909090",
         "899640030000E9C4CBFEFF"),
        (0x12D1, "90909090909090909090909090",
         "85C00F846E7F0000E993080000"),
        (0x1B71, "9090909090909090909090",
         "8D90D40D0000E995040000"),
        (0x2011, "9090909090909090909090",
         "3B963C030000E9650C0000"),
        (0x2C81, "90909090909090909090909090",
         "0F850A6700008B0AE9C3140000"),
        (0x4151, "9090909090909090909090",
         "334A04324AF4E945490000"),
        (0x8AA1, "9090909090909090909090",
         "3B8E40030000E995070000"),
        (0x9241, "909090909090909090",
         "0F854A010000C20400"),
        (0x9391, "909090909090909090",
         "8D8670F5FFFFC20400"),
        (0x20631, "9090909090909090909090909090",
         "FF742404E806C20300E9920CFEFF"),
        (0x6E449, "E852EDF9FF",
         "E82321FBFF"),
        (0x6E516, "E885ECF9FF",
         "E85620FBFF"),
        (0x6E492, "E8A9E3FEFF",
         "E89A21FBFF"),
        (0x6E56D, "E8CEE2FEFF",
         "E8BF20FBFF"),
    ),
    "vv4": (
        (0x1EA4C, "D8000000",
         "00010000"),
        (0x152C1, "CCCCCCCCCCCCCCCCCCCCCCCCCCCCCC",
         "8B4424048986D8000000E9D1000000"),
        (0x153A1, "CCCCCCCCCCCCCCCCCCCCCCCCCC",
         "8B103350043250F4E903020000"),
        (0x155B1, "CCCCCCCCCCCCCCCCCCCCCC",
         "8996DC000000E9247EFFFF"),
        (0x15751, "CCCCCCCCCCCCCCCCCCCCCCCCCCCC",
         "FF742404E8E6080500E9D2000000"),
        (0x15831, "CCCCCCCCCCCCCCCCCCCCCCCCCC",
         "85C00F840E060000E993000000"),
        (0x158D1, "CCCCCCCCCCCCCCCCCCCCCC",
         "8D909C1B0000E955010000"),
        (0x15A31, "CCCCCCCCCCCCCCCCCCCCCC",
         "3B96D8000000E9D5000000"),
        (0x15B11, "CCCCCCCCCCCCCCCCCCCCCCCCCC",
         "0F857A0400008B0AE9F3000000"),
        (0x15C11, "CCCCCCCCCCCCCCCCCCCCCC",
         "334A04324AF4E995010000"),
        (0x15DB1, "CCCCCCCCCCCCCCCCCCCCCC",
         "3B8EDC000000E985000000"),
        (0x15E41, "CCCCCCCCCCCCCCCCCC",
         "0F854A010000C20400"),
        (0x15F91, "CCCCCCCCCCCCCCCCCC",
         "8D8644E5FFFFC20400"),
        (0x48516, "E8C54EFCFF",
         "E8A6CDFCFF"),
        (0x485F3, "E8E84DFCFF",
         "E8C9CCFCFF"),
        (0x4856C, "E8CFDA0100",
         "E8E0D1FCFF"),
        (0x48653, "E8E8D90100",
         "E8F9D0FCFF"),
    ),
    "vv5": (
        (0x23EFC, "EC000000",
         "14010000"),
        (0x15781, "CCCCCCCCCCCCCCCCCCCCCCCCCCCCCC",
         "8B4424048986EC000000E941000000"),
        (0x157D1, "CCCCCCCCCCCCCCCCCCCCCCCCCC",
         "8B103350043250F4E9D3000000"),
        (0x158B1, "CCCCCCCCCCCCCCCCCCCCCC",
         "8996F0000000E91480FFFF"),
        (0x15AA1, "CCCCCCCCCCCCCCCCCCCCCCCCCCCC",
         "FF742404E8A69E0500E982000000"),
        (0x15B31, "CCCCCCCCCCCCCCCCCCCCCCCCCC",
         "85C00F84EE0A0000E983010000"),
        (0x15CC1, "CCCCCCCCCCCCCCCCCCCCCC",
         "8D909C1B0000E9A5000000"),
        (0x15D71, "CCCCCCCCCCCCCCCCCCCCCC",
         "3B96EC000000E925010000"),
        (0x15EA1, "CCCCCCCCCCCCCCCCCCCCCCCCCC",
         "0F85AA0800008B0AE963020000"),
        (0x16111, "CCCCCCCCCCCCCCCCCCCCCC",
         "334A04324AF4E9E5010000"),
        (0x16301, "CCCCCCCCCCCCCCCCCCCCCC",
         "3B8EF0000000E915030000"),
        (0x16621, "CCCCCCCCCCCCCCCCCC",
         "0F852A010000C20400"),
        (0x16751, "CCCCCCCCCCCCCCCCCC",
         "8D8658E5FFFFC20400"),
        (0x4BB26, "E8A51DFCFF",
         "E8569CFCFF"),
        (0x4BC03, "E8C81CFCFF",
         "E8799BFCFF"),
        (0x4BB7C, "E8CF3D0200",
         "E8209FFCFF"),
        (0x4BC63, "E8E83C0200",
         "E8399EFCFF"),
    ),
}


def name_identity_fixes(game: str) -> tuple:
    return tuple((off, bytes.fromhex(b), bytes.fromhex(a)) for off, b, a in NAME_IDENTITY_FIXES[game])

_CACHE: dict = {}


def _render(game: str, mode: str, ids) -> bytes:
    key = (game, mode, tuple(ids))
    if key not in _CACHE:
        build = next(b for b in load_builds() if b.id == game)
        rendered, _ = render_patched_bytes(STOCK_DIR / EXES[game], build, mode, list(ids))
        _CACHE[key] = bytes(rendered)
    return _CACHE[key]


def _builds(game: str):
    """(mode, label, exe, fixed, full_names) for every combination."""
    fix, full = game + "_fix_vanilla_bugs", game + "_details_full_names"
    for mode in MODES:
        for label, ids in (("stock", []), ("full names", [full]), ("fixed", [fix]), ("fixed + full names", [fix, full])):
            yield mode, label, _render(game, mode, ids), label.startswith("fixed"), "full names" in label


# ---------------------------------------------------------------- A New Home

class ANewHomeIdentityTests(unittest.TestCase):
    """The reload-flag guard alone (cd8c1de1) wrote the box into whatever the
    selection named once the box had been refilled; the identity check also
    refuses a record that no longer holds the villager the box was filled for."""

    NAMES = ["Tiki Alosaka", "Iruwa Okelani", "Kito Kalahuna", "Chika Kalahuna"]

    def _screen(self, exe, selected=0):
        s = DetailsScreen(exe, self.NAMES, selected)
        for k in range(4):
            s.mu.mem_write(0x22000000 + k * STRIDE + 0x350, struct.pack("<i", 1 + k % 2))
        return s

    def test_record_reused_while_the_box_shows_someone_else(self) -> None:
        for mode, label, exe, fixed, full in _builds("vv1"):
            with self.subTest(mode=mode, build=label):
                s = self._screen(exe)
                s.frame()
                self.assertEqual(s.box(), "Tiki Alosaka")
                # record 0 now holds another villager (another name and sex)
                s.mu.mem_write(0x22000000 + NAME, b"Leilani Kahale\0".ljust(28, b"\0"))
                s.mu.mem_write(0x22000000 + 0x350, struct.pack("<i", 2))
                s.click(DONE_ID)
                cut = 27 if full else 10
                self.assertEqual(s.name(0), "Leilani Kahale" if fixed else "Tiki Alosaka"[:cut])

    def test_selection_moved_without_a_refill(self) -> None:
        for mode, label, exe, fixed, full in _builds("vv1"):
            with self.subTest(mode=mode, build=label):
                s = self._screen(exe)
                s.frame()
                s.mu.mem_write(0x21000000 + 0xAD34, struct.pack("<i", 1))   # the reload flag stays clear
                s.click(DONE_ID)
                cut = 27 if full else 10
                self.assertEqual(s.name(1), "Iruwa Okelani" if fixed else "Tiki Alosaka"[:cut])

    def test_typed_name_after_the_guard_still_saves(self) -> None:
        for mode, label, exe, fixed, full in _builds("vv1"):
            with self.subTest(mode=mode, build=label):
                s = self._screen(exe)
                s.frame()
                s.type_name("Moana")
                s.click(NEXT_ID)
                s.frame()
                s.type_name("Kai")
                s.click(DONE_ID)
                self.assertEqual([s.name(i) for i in range(2)], ["Moana", "Kai"])

    def test_a_dropped_box_is_refilled_with_the_right_name(self) -> None:
        for mode, label, exe, fixed, full in _builds("vv1"):
            if not fixed:
                continue
            with self.subTest(mode=mode, build=label):
                s = self._screen(exe)
                s.frame()
                s.mu.mem_write(0x22000000 + NAME, b"Leilani Kahale\0".ljust(28, b"\0"))
                s.click(NEXT_ID)             # the write-back is refused, the arrow still moves
                s.frame()
                self.assertEqual(s.name(0), "Leilani Kahale")
                self.assertEqual(s.box(), "Iruwa Okelani")


# ------------------------------------------------------ the four later games

STACK = 0x70000000
SCREEN = 0x20000000
GAME = 0x21000000
ARRAY = 0x22000000
BOX = 0x26000000
BOX_TEXT = BOX + 0x1000
RETURN = 0x0BAD0000

LATER = {
    # show/select/handler entries, the name box field, Done's id field, the
    # selection (game getter + field, or VV2's state +0x304F0), the record
    # lookup, and the engine routines the code calls (stubbed: address -> (kind, bytes popped)).
    "vv3": dict(stride=0x1F8C, name=0xDD4, sex=0xDC8, show=0x46E410, select=0x46E460, handler=0x46E530,
                box=0x308, done=0x2BC, game_get=0x428B60, sel=0x12FC0, lookup=0x45C840, table=None,
                stubs={0x46E280: ("nop", 0), 0x46E390: ("nop", 0), 0x45EE60: ("one", 4), 0x45FCC0: ("nop", 0),
                       0x424110: ("nop", 4), 0x40C480: ("nop", 4), 0x40D1E0: ("get", 8), 0x40D1A0: ("set", 4),
                       0x46F780: ("ncpy", 0)}),
    "vv4": dict(stride=0x2E3C, name=0x1B9C, sex=0x1B90, show=0x4484E0, select=0x448520, handler=0x448610,
                box=0xA4, done=0x58, game_get=0x41FE70, sel=0x171B0, lookup=0x466040, table=0x4D8E00,
                stubs={0x448290: ("nop", 0), 0x448400: ("nop", 0), 0x467980: ("one", 4), 0x40D3F0: ("one", 0),
                       0x466BE0: ("nop", 0), 0x45DCD0: ("nop", 4), 0x47108D: ("nop", 0), 0x448E10: ("nop", 4),
                       0x40C3E0: ("nop", 4), 0x40D420: ("get", 8), 0x40D3E0: ("set", 4), 0x4724E0: ("ncpy", 0)}),
    "vv5": dict(stride=0x2F44, name=0x1B9C, sex=0x1B90, show=0x44BAF0, select=0x44BB30, handler=0x44BC20,
                box=0xA8, done=0x58, game_get=0x425950, sel=0x17E24, lookup=0x46F950, table=0x51E220,
                stubs={0x44B890: ("nop", 0), 0x44BA10: ("nop", 0), 0x471840: ("one", 4), 0x40D8E0: ("one", 0),
                       0x470800: ("nop", 0), 0x465360: ("nop", 4), 0x47C00D: ("nop", 0), 0x44C440: ("nop", 4),
                       0x40C8D0: ("nop", 4), 0x40D910: ("get", 8), 0x40D8D0: ("set", 4), 0x47D7C0: ("ncpy", 0)}),
    "vv2": dict(stride=0xE48C, name=0x564, sex=0x538, show=0x466370, select=None, handler=0x467720,
                box=0x500, done=0x4B8, next=0x4C4, game_get=None, sel=0x304F0, lookup=None, table=None,
                stubs={0x4661E0: ("count", 0), 0x465F80: ("nop", 4), 0x466080: ("nop", 4), 0x465E80: ("nop", 4),
                       0x43F010: ("nop", 4), 0x466330: ("pos", 4), 0x4491F0: ("nop", 0), 0x40B7F0: ("nop", 4),
                       0x40C550: ("getdirect", 8), 0x40C510: ("set", 4)}),
}


class LaterDetails:
    """One rendered executable's real Details show / arrow / Done code."""

    def __init__(self, game: str, exe: bytes, names: list[str]) -> None:
        self.g = g = LATER[game]
        self.game = game
        image = pefile.PE(data=exe).get_memory_mapped_image()
        self.mu = mu = Uc(UC_ARCH_X86, UC_MODE_32)
        mu.mem_map(0x400000, (len(image) + 0xFFFF) & ~0xFFFF)
        mu.mem_write(0x400000, image)
        mu.mem_map(STACK - 0x10000, 0x20000)
        for base, size in ((SCREEN, 0x10000), (GAME, 0x40000), (ARRAY, 0x40000), (BOX, 0x10000), (RETURN, 0x1000)):
            mu.mem_map(base, size)
        self.count = len(names)
        for k, name in enumerate(names):
            self.put(k, name, k % 2)
        if game == "vv2":
            mu.mem_write(SCREEN + 0x0C, struct.pack("<I", GAME))
            mu.mem_write(SCREEN + 0x10, struct.pack("<I", ARRAY))
            mu.mem_write(SCREEN + g["next"], struct.pack("<I", 0x301))
            for k in range(len(names)):                       # the screen's own order list (+0x30)
                mu.mem_write(SCREEN + 0x30 + 4 * k, struct.pack("<I", k))
        if game == "vv3":
            for k in range(len(names)):                       # the arrows' order list (+0x08)
                mu.mem_write(SCREEN + 8 + 4 * k, struct.pack("<I", k))
        if g["table"]:
            for k in range(len(names)):                       # the arrows' order table
                mu.mem_write(g["table"] + 4 * k, struct.pack("<I", k))
        mu.mem_write(SCREEN + g["box"], struct.pack("<I", BOX))
        mu.mem_write(SCREEN + g["done"], struct.pack("<I", 0x300))
        self.select_index(0)
        mu.hook_add(UC_HOOK_CODE, self._on_code)

    # records
    def rec(self, k: int) -> int:
        return ARRAY + k * self.g["stride"]

    def put(self, k: int, name: str, sex: int) -> None:
        self.mu.mem_write(self.rec(k) + self.g["name"], name.encode("latin-1").ljust(25, b"\0")[:25])
        self.mu.mem_write(self.rec(k) + self.g["sex"], struct.pack("<i", sex))

    def name(self, k: int) -> str:
        return bytes(self.mu.mem_read(self.rec(k) + self.g["name"], 25)).split(b"\0")[0].decode("latin-1")

    def select_index(self, k: int) -> None:
        self.mu.mem_write(GAME + self.g["sel"], struct.pack("<i", k))

    def selected(self) -> int:
        return struct.unpack("<i", self.mu.mem_read(GAME + self.g["sel"], 4))[0]

    def box(self) -> str:
        return bytes(self.mu.mem_read(BOX_TEXT, 64)).split(b"\0")[0].decode("latin-1")

    def type_name(self, text: str) -> None:
        self.mu.mem_write(BOX_TEXT, text.encode("latin-1") + b"\0")

    # the engine
    def _ret(self, uc, value: int, pop: int) -> None:
        esp = uc.reg_read(UC_X86_REG_ESP)
        ret = struct.unpack("<I", uc.mem_read(esp, 4))[0]
        uc.reg_write(UC_X86_REG_EAX, value & 0xFFFFFFFF)
        uc.reg_write(UC_X86_REG_ESP, esp + 4 + pop)
        uc.reg_write(UC_X86_REG_EIP, ret)

    def _on_code(self, uc, address, size, user_data) -> None:
        g = self.g
        esp = uc.reg_read(UC_X86_REG_ESP)
        a1, a2, a3 = struct.unpack("<III", uc.mem_read(esp + 4, 12))
        if address == g.get("game_get"):
            return self._ret(uc, GAME, 0)
        if address == g.get("lookup"):
            return self._ret(uc, self.rec(a1) if 0 <= a1 < self.count else 0, 4)
        if address not in g["stubs"]:
            return
        kind, pop = g["stubs"][address]
        value = 0
        if kind == "one":
            value = 1
        elif kind == "set":
            text = bytes(uc.mem_read(a1, 64)).split(b"\0")[0]
            uc.mem_write(BOX_TEXT, text + b"\0")
        elif kind in ("get", "getdirect"):
            text = bytes(uc.mem_read(BOX_TEXT, 64)).split(b"\0")[0][:a2 - 1]
            uc.mem_write(a1, text + b"\0")
        elif kind == "ncpy":
            src = bytes(uc.mem_read(a2, a3)).split(b"\0")[0][:a3]
            uc.mem_write(a1, src.ljust(a3, b"\0"))
        elif kind == "count":
            value = self.count
        elif kind == "pos":
            value = a1
        self._ret(uc, value, pop)

    def _call(self, entry: int, *args: int) -> None:
        esp = STACK - 0x200 - 4 * len(args)
        self.mu.mem_write(esp, struct.pack("<I" + "I" * len(args), RETURN, *args))
        self.mu.reg_write(UC_X86_REG_ESP, esp)
        self.mu.reg_write(UC_X86_REG_ECX, SCREEN)
        self.mu.emu_start(entry, RETURN, count=400000)

    # what the player does
    def show(self) -> None:
        self._call(self.g["show"], 1)

    def done(self) -> None:
        self._call(self.g["handler"], 8, 0x300)

    def next(self) -> None:
        if self.game == "vv2":
            self._call(self.g["handler"], 8, 0x301)
        else:
            self._call(self.g["select"], (self.selected() + 1) % self.count)


class LaterGamesIdentityTests(unittest.TestCase):
    NAMES = ["Tiki", "Iruwa", "Kito", "Chika"]

    def screens(self):
        for game in ("vv2", "vv3", "vv4", "vv5"):
            for mode, label, exe, fixed, full in _builds(game):
                yield game, mode, label, exe, fixed

    def test_record_reused_while_the_screen_is_open(self) -> None:
        for game, mode, label, exe, fixed in self.screens():
            with self.subTest(game=game, mode=mode, build=label):
                s = LaterDetails(game, exe, self.NAMES)
                s.show()
                self.assertEqual(s.box(), "Tiki")
                s.put(0, "Leilani", 1)              # another villager now holds record 0
                s.done()
                self.assertEqual(s.name(0), "Leilani" if fixed else "Tiki")
                if fixed:
                    s.show()
                    self.assertEqual(s.box(), "Leilani")

    def test_selection_moved_without_a_refill(self) -> None:
        for game, mode, label, exe, fixed in self.screens():
            with self.subTest(game=game, mode=mode, build=label):
                s = LaterDetails(game, exe, self.NAMES)
                s.show()
                s.select_index(2)
                s.done()
                self.assertEqual(s.name(2), "Kito" if fixed else "Tiki")

    def test_typed_names_still_save_to_the_villager_shown(self) -> None:
        for game, mode, label, exe, fixed in self.screens():
            with self.subTest(game=game, mode=mode, build=label):
                s = LaterDetails(game, exe, self.NAMES)
                s.show()
                s.type_name("Moana")
                s.next()
                self.assertEqual(s.selected(), 1)
                self.assertEqual(s.box(), "Iruwa")
                s.type_name("Kai")
                s.done()
                self.assertEqual([s.name(k) for k in range(4)], ["Moana", "Kai", "Kito", "Chika"])

    def test_256_villager_builds(self) -> None:
        """The 256 Villagers (Experimental) builds keep the guard: it uses the
        game's own record lookup and the screen object, never a table address."""
        for game in ("vv3", "vv4", "vv5"):
            for mode in MODES:
                exe = _render(game, mode, [game + "_fix_vanilla_bugs", game + "_population_256"])
                with self.subTest(game=game, mode=mode):
                    s = LaterDetails(game, exe, self.NAMES)
                    s.show()
                    s.put(0, "Leilani", 1)
                    s.done()
                    self.assertEqual(s.name(0), "Leilani")
                    s.show()
                    s.type_name("Moana")
                    s.done()
                    self.assertEqual(s.name(0), "Moana")

    def test_an_untouched_box_changes_nothing(self) -> None:
        for game, mode, label, exe, fixed in self.screens():
            with self.subTest(game=game, mode=mode, build=label):
                s = LaterDetails(game, exe, self.NAMES)
                s.show()
                for _ in range(5):
                    s.next()
                    self.assertEqual(s.box(), self.NAMES[s.selected()])
                s.done()
                self.assertEqual([s.name(k) for k in range(4)], self.NAMES)


class StaticTests(unittest.TestCase):
    """Every fill and every write-back of each game's Details name box goes
    through the guard, and the padding the guard code lives in is padding
    nothing jumps into."""

    # game: (fill sites, original fill callee, write-back sites, original write-back callee)
    SITES = {
        "vv1": ([0x44A66A], 0x44F380, [0x44A748, 0x44A7A4, 0x44A859], 0x44A6F2),
        "vv2": ([0x4663A6, 0x467945], 0x40C510, [0x467767, 0x4677F8, 0x4678C6], 0x40C550),
        "vv3": ([0x46E449, 0x46E516], 0x40D1A0, [0x46E492, 0x46E56D], 0x45C840),
        "vv4": ([0x448516, 0x4485F3], 0x40D3E0, [0x44856C, 0x448653], 0x466040),
        "vv5": ([0x44BB26, 0x44BC03], 0x40D8D0, [0x44BB7C, 0x44BC63], 0x46F950),
    }

    @staticmethod
    def _target(image: bytes, site: int) -> int:
        assert image[site - 0x400000] == 0xE8, hex(site)
        return site + 5 + struct.unpack_from("<i", image, site - 0x400000 + 1)[0]

    def test_sites_are_hooked_and_the_code_sits_in_padding(self) -> None:
        for game, (fills, fill_callee, writes, write_callee) in self.SITES.items():
            with self.subTest(game=game):
                stock = pefile.PE(data=(STOCK_DIR / EXES[game]).read_bytes()).get_memory_mapped_image()
                fixed = pefile.PE(data=_render(game, "stock", [game + "_fix_vanilla_bugs"])).get_memory_mapped_image()
                fill_entries = {self._target(fixed, s) for s in fills}
                write_entries = {self._target(fixed, s) for s in writes}
                self.assertEqual(len(fill_entries), 1)
                self.assertEqual(len(write_entries), 1)
                if game != "vv1":
                    for s in writes:
                        self.assertEqual(self._target(stock, s), write_callee)
                for s in fills:
                    if game != "vv1":
                        self.assertEqual(self._target(stock, s), fill_callee)
                # the fill and check code: every byte that changed outside the
                # Details code was padding (int3 / nop) in the stock game, or the
                # tail of Fix Vanilla Bugs' own rewritten functions (vv1, vv2)
                changed = [a for a in range(len(stock)) if stock[a] != fixed[a]]
                pad = [a for a in changed if stock[a] in (0xCC, 0x90)]
                for entry in fill_entries | write_entries:
                    if game in ("vv3", "vv4", "vv5"):
                        self.assertIn(entry - 0x400000, pad)

    def test_screen_objects_grow(self) -> None:
        # game: (push VA, stock size, fixed size)
        sizes = {"vv1": (0x41B755, 0xCC, 0xD4), "vv2": (0x424205, 0x54C, 0x554), "vv3": (0x427A38, 0x33C, 0x364),
                 "vv4": (0x41EA4B, 0xD8, 0x100), "vv5": (0x423EFB, 0xEC, 0x114)}
        for game, (va, old, new) in sizes.items():
            with self.subTest(game=game):
                stock = (STOCK_DIR / EXES[game]).read_bytes()
                fixed = _render(game, "stock", [game + "_fix_vanilla_bugs"])
                o = pefile.PE(data=stock).get_offset_from_rva(va - 0x400000)
                self.assertEqual(stock[o:o + 5], b"\x68" + struct.pack("<I", old))
                self.assertEqual(fixed[o:o + 5], b"\x68" + struct.pack("<I", new))


if __name__ == "__main__":
    unittest.main()


