"""Skin tones: the draws of The Secret City, The Tree of Life and New Believers ("VVFP Skin Tones.dll").

The DLL is run in the emulated game (tests/story_emulator.py, the Head Look's village and disk).  In The
Tree of Life and New Believers each site is the game's own `call` of the routine that fetches a villager's
head or body sheet, pointed at a stub that calls that routine and then hands on the villager's tone's copy
of the sheet.  In The Secret City the sites are the entries of the village's draw and of the thunk the
Villager Details portrait and an island event's figure call, where the sheet is the first argument.

Proved here, per game: every site installed, or none (a site that does not hold the game's own bytes; another
game); the fetcher gets the game's own arguments and its answer comes back untouched; a villager with a tone
gets that tone's sheet, built once by the game's own constructor from the game's own description of the
sheet, under the name "vvfp_skin_<NN>_<the game's name>"; the game's own sheet stays when a picture of the
set is missing, when the load fails, for Default, for a register that is no villager, and for a sheet that
is not a villager's (a mask); and all of it in the patcher's three modes with every patch.

The game's fetcher, allocator and sheet constructor are stood in for (they read the picture files through
the engine); the pictures are names on the emulator's disk -- a test-only sheet, nothing drawn.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

try:
    import pefile

    from head_look_emulation import Game
    from story_emulator import STACK_TOP
    from test_head_look import MODES, rendered, stock_exe, stock_path

    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

DLL = ROOT / "assets" / "skin_tones" / "VVFP Skin Tones.dll"
GAMES_OWN = 15

# native/vvfp_skin_tones/vvfp_skin_tones.c VV4_DRAWS / VV5_DRAWS.
DRAWS = {
    4: dict(alloc=0x470C5C, grid=0x40ABA0, one=0x40AB10, sheets=0x4C3B88, table=0x4E00E0,
            head=0x44EA00, body=0x44E960, head_sites=(0x467F36, 0x45F6BA, 0x45F99C),
            body_sites=(0x4681C7, 0x45F616, 0x45F917), not_sites=(0x43D00F, 0x43CF8C)),
    5: dict(alloc=0x47BBDC, grid=0x40B0A0, one=0x40B010, sheets=0x4D1DA8, table=0x5258B8,
            head=0x451DA0, body=0x451D00, head_sites=(0x47233B, 0x466DB7, 0x4670CC),
            body_sites=(0x472683, 0x466D17, 0x467047), not_sites=(0x43F8DF, 0x43F85C)),
}
SHEETS = ("female_heads", "female_bodies", "female_actions", "male_heads", "male_bodies", "male_actions",
          "bigheads", "bigbodies.png")
# files across, down; columns, rows -- the game's own descriptions (checked in test_the_sheet_descriptions).
GRIDS = ((2, 1, 16, 30), (2, 3, 32, 30), (1, 3, 17, 30), (2, 1, 16, 30), (2, 3, 32, 30), (1, 3, 17, 30),
         (2, 1, 12, 30), (0, 0, 2, 30))


def have(game: int) -> bool:
    return HAVE_EMULATOR and stock_path(game).is_file() and DLL.is_file()


class Draws:
    """One game with the DLL started, a villager, and the engine's routines stood in for."""

    def __init__(self, game: int, exe: bytes | None = None, start: bool = True):
        self.game, self.d = game, DRAWS[game]
        self.g = Game(game, exe if exe is not None else stock_exe(game), start=False, dll=DLL)
        p = self.p = self.g.p
        p.api_handlers["QueryPerformanceCounter"] = self._counter
        self.own = []                       # the game's own eight sheets, as its registry holds them
        for k in range(8):
            sheet = p.alloc(0x40)
            p.put32(self.d["sheets"] + k * 0x30 + 0x2C, sheet)
            self.own.append(sheet)
        self.fetched, self.built, self.fail_load = [], [], False
        self.next_sheet = self.own[3]
        p.stub(self.d["head"], lambda p: self._fetch(p, 5, 0x1C))
        p.stub(self.d["body"], lambda p: self._fetch(p, 6, 0x20))
        p.stub(self.d["alloc"], lambda p: (p.alloc(0x70), 0))
        p.stub(self.d["grid"], lambda p: self._construct(p, 6))
        p.stub(self.d["one"], lambda p: self._construct(p, 3))
        if start:
            p.export("VvfpStartup", game, 0)
        self.images = p.exe_path.decode().rsplit("\\", 1)[0] + "\\Images\\"

    def _counter(self, p):
        p.write(p.arg(0), struct.pack("<Q", 0x1234567))
        return 1, 4

    def _fetch(self, p, out_at: int, pop: int):
        """The game's fetcher: the sheet through its out pointer, its first argument back."""
        args = [p.arg(i) for i in range(pop // 4)]
        self.fetched.append((p.reg("ecx"), args))
        if args[out_at]:
            p.put32(args[out_at], self.next_sheet)
        return args[0], pop

    def _construct(self, p, count: int):
        obj = p.reg("ecx")
        args = [p.arg(i) for i in range(count)]
        name = p.cstring(args[0])
        self.built.append((name,) + ((p.cstring(args[1]),) + tuple(args[2:]) if count == 6 else tuple(args[1:])))
        p.put32(obj + 0x10, 0 if self.fail_load else 40)       # the cell width: 0 after a load that failed
        return obj, 4 * count

    def picture(self, tone: int, k: int, missing: int = -1) -> None:
        """Every file of tone `tone`'s copy of sheet `k` on the disk (but number `missing`)."""
        across, down, _, _ = GRIDS[k]
        base = f"vvfp_skin_{tone:02d}_{SHEETS[k]}"
        names = [f"{base}{a}{d}.png" for a in range(across) for d in range(down)] if across else [base]
        for n, name in enumerate(names):
            if n != missing:
                self.g.disk.files[(self.images + name).lower()] = b"png"

    def villager(self, tone: int, i: int = 3) -> int:
        record = self.g.villager(i, f"Keoni{i}", age=600)
        if tone:
            self.g.later()
            assert self.p.export("VvfpSkinToneSet", self.game, record, tone) == 1
        return record

    def draw(self, site: int, record: int, sheet: int) -> int:
        """Run the site's `call` as the game reaches it; the sheet the draw would then use."""
        p, head = self.p, site in self.d["head_sites"] or site == self.d["not_sites"][0]
        count = 7 if head else 8
        esp = STACK_TOP - 0x4000
        out, point = p.alloc(8), p.alloc(8)
        args = [point, 5, 0, 7, 0x3F800000, out, 0] if head else [point, 3, 0, 9, 4, 0x3F800000, out, 0]
        for i, value in enumerate(args):
            p.put32(esp + 4 * i, value)
        p.put32(out, 0)
        self.next_sheet = sheet
        self.fetched.clear()
        self.g.later()
        for name, value in (("esp", esp), ("esi", record), ("ecx", self.d["table"]), ("ebx", 0x11111111),
                            ("edi", 0x22222222), ("ebp", 0x33333333)):
            p.set_reg(name, value)
        p.run(site, site + 5)
        assert p.reg("esp") == esp + 4 * count, "the fetcher's arguments were not popped once"
        assert p.reg("eax") == point, "the fetcher's answer did not come back"
        assert (p.reg("esi"), p.reg("ebx"), p.reg("edi"), p.reg("ebp")) == (record, 0x11111111, 0x22222222, 0x33333333)
        assert self.fetched == [(self.d["table"], args)], "the fetcher did not get the game's own arguments"
        return p.u32(out)


class _Base:
    GAME = 0

    def sites(self):
        d = DRAWS[self.GAME]
        return [(va, d["head"]) for va in d["head_sites"]] + [(va, d["body"]) for va in d["body_sites"]]

    def stock_call(self, va: int, target: int) -> bytes:
        return b"\xE8" + struct.pack("<i", target - (va + 5))

    def test_the_sites_are_the_games_own_calls(self):
        pe = pefile.PE(data=stock_exe(self.GAME))
        image, base = pe.get_memory_mapped_image(), pe.OPTIONAL_HEADER.ImageBase
        d = DRAWS[self.GAME]
        for va, target in self.sites() + [(d["not_sites"][0], d["head"]), (d["not_sites"][1], d["body"])]:
            with self.subTest(site=hex(va)):
                self.assertEqual(image[va - base:va - base + 5], self.stock_call(va, target))

    def test_the_sheet_descriptions(self):
        pe = pefile.PE(data=stock_exe(self.GAME))
        image, base = pe.get_memory_mapped_image(), pe.OPTIONAL_HEADER.ImageBase
        for k, name in enumerate(SHEETS):
            at = DRAWS[self.GAME]["sheets"] + k * 0x30 - base
            fields = struct.unpack_from("<8I", image, at)
            got = image[fields[1] - base:fields[1] - base + 32].split(b"\0")[0].decode()
            with self.subTest(sheet=name):
                self.assertEqual((got, fields[5], fields[6], fields[2], fields[3]), (name,) + GRIDS[k])

    def test_installs_every_site(self):
        t = Draws(self.GAME)
        self.assertEqual(t.p.export("VvfpSkinToneDrawn", self.GAME), 1)
        for va, target in self.sites():
            with self.subTest(site=hex(va)):
                now = t.p.read(va, 5)
                self.assertEqual(now[:1], b"\xE8")
                self.assertNotEqual(now, self.stock_call(va, target))
        for va, target in zip(DRAWS[self.GAME]["not_sites"], (DRAWS[self.GAME]["head"], DRAWS[self.GAME]["body"])):
            self.assertEqual(t.p.read(va, 5), self.stock_call(va, target), "the memorial list is left alone")

    def test_all_or_nothing(self):
        for va, _ in self.sites():
            for k in (0, 4):
                exe = bytearray(stock_exe(self.GAME))
                pe = pefile.PE(data=bytes(exe))
                exe[pe.get_offset_from_rva(va + k - 0x400000)] ^= 0xFF
                t = Draws(self.GAME, bytes(exe))
                with self.subTest(site=hex(va), byte=k):
                    self.assertEqual(t.p.export("VvfpSkinToneDrawn", self.GAME), 0)
                    for other, target in self.sites():
                        if other != va:
                            self.assertEqual(t.p.read(other, 5), self.stock_call(other, target))

    def test_another_game_installs_nothing(self):
        t = Draws(self.GAME, start=False)
        t.p.export("VvfpStartup", 3, 0)
        self.assertEqual(t.p.export("VvfpSkinToneDrawn", self.GAME), 0)
        for va, target in self.sites():
            self.assertEqual(t.p.read(va, 5), self.stock_call(va, target))

    def test_a_villager_with_a_tone_is_drawn_from_that_tones_sheet(self):
        t = Draws(self.GAME)
        record = t.villager(7)
        for k in range(8):
            t.picture(7, k)
        seen = {}
        for site, _ in self.sites():
            head = site in DRAWS[self.GAME]["head_sites"]
            for k in ((0, 3, 6) if head else (1, 2, 4, 5, 7)):
                with self.subTest(site=hex(site), sheet=SHEETS[k]):
                    got = t.draw(site, record, t.own[k])
                    self.assertNotIn(got, t.own, "the game's own sheet was handed on")
                    self.assertNotEqual(got, 0)
                    self.assertEqual(seen.setdefault(k, got), got, "one sheet for a tone, however often drawn")
        across = {k: GRIDS[k] for k in range(8)}
        expected = sorted(
            (f"vvfp_skin_07_{SHEETS[k]}",) + ((".png",) + across[k] if across[k][0] else across[k][2:]) for k in range(8))
        self.assertEqual(sorted(t.built), expected, "each built once, by the game's own description")

    def test_another_tone_is_another_sheet(self):
        t = Draws(self.GAME)
        a, b = t.villager(2, 3), t.villager(9, 4)
        t.picture(2, 3)
        t.picture(9, 3)
        site = DRAWS[self.GAME]["head_sites"][0]
        first, second = t.draw(site, a, t.own[3]), t.draw(site, b, t.own[3])
        self.assertNotEqual(first, second)
        self.assertEqual({name for name, *_ in t.built}, {"vvfp_skin_02_male_heads", "vvfp_skin_09_male_heads"})

    def test_the_games_own_sheet_when_the_tones_is_not_all_there(self):
        site = DRAWS[self.GAME]["body_sites"][0]
        for missing in range(6):                            # male_bodies is six files
            t = Draws(self.GAME)
            record = t.villager(5)
            t.picture(5, 4, missing=missing)
            with self.subTest(missing=missing):
                self.assertEqual(t.draw(site, record, t.own[4]), t.own[4])
                self.assertEqual(t.built, [], "nothing is loaded from half a set")
        t = Draws(self.GAME)
        record = t.villager(5)
        self.assertEqual(t.draw(site, record, t.own[7]), t.own[7], "no picture at all")
        t.picture(5, 4)
        self.assertNotIn(t.draw(site, record, t.own[4]), t.own, "the whole set is there")
        self.assertEqual(t.draw(site, record, t.own[1]), t.own[1], "the women's bodies of that tone are not there")

    def test_a_load_that_fails_keeps_the_games_own(self):
        t = Draws(self.GAME)
        record = t.villager(5)
        t.picture(5, 3)
        t.fail_load = True
        site = DRAWS[self.GAME]["head_sites"][0]
        self.assertEqual(t.draw(site, record, t.own[3]), t.own[3])
        t.fail_load = False
        self.assertEqual(t.draw(site, record, t.own[3]), t.own[3], "tried once, not again in this session")
        self.assertEqual(len(t.built), 1)

    def test_default_and_no_villager_and_other_sheets_are_the_games_own(self):
        t = Draws(self.GAME)
        record = t.villager(GAMES_OWN)
        for k in range(8):
            for tone in range(1, 11):
                t.picture(tone, k)
        head, body = DRAWS[self.GAME]["head_sites"][0], DRAWS[self.GAME]["body_sites"][0]
        self.assertEqual(t.draw(head, record, t.own[3]), t.own[3], "Default chosen")
        self.assertEqual(t.draw(body, record, t.own[4]), t.own[4], "Default chosen")
        toned = t.villager(4, 6)
        mask_sheet = t.p.alloc(0x40)
        self.assertEqual(t.draw(head, toned, mask_sheet), mask_sheet, "a sheet that is not a villager's (a mask)")
        self.assertEqual(t.draw(head, toned + 8, t.own[3]), t.own[3], "ESI is not a villager's record")
        self.assertEqual(t.draw(head, t.g.record(40), t.own[3]), t.own[3], "a record nobody holds")
        self.assertEqual(t.built, [])
        self.assertNotIn(t.draw(head, toned, t.own[3]), t.own, "and the villager with a tone is still toned")

    def test_every_mode_with_every_patch(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                t = Draws(self.GAME, rendered(self.GAME, mode))
                self.assertEqual(t.p.export("VvfpSkinToneDrawn", self.GAME), 1)
                record = t.villager(8)
                t.picture(8, 0)
                t.picture(8, 1)
                d = DRAWS[self.GAME]
                self.assertNotIn(t.draw(d["head_sites"][0], record, t.own[0]), t.own)
                self.assertNotIn(t.draw(d["body_sites"][0], record, t.own[1]), t.own)
                self.assertEqual(t.draw(d["body_sites"][0], record, t.own[4]), t.own[4])


# ---- The Secret City ------------------------------------------------------------------------------

VV3 = dict(alloc=0x46EC93, grid=0x40AF90, one=0x40AF10, sheets=0x4AAE60, slots=0x59E110 + 0x127C20,
           slot_at=(0x10, 0x18, 0x00, 0x08, 0x14, 0x1C, 0x04, 0x0C), village=0x42E5E0, thunk=0x409FB0,
           entry=0x4093A0, renderer=0x58F6F8)
SHEETS3 = ("female_heads.png", "female_heads_old.png", "female_bodies", "female_actions", "male_heads.png",
           "male_heads_old.png", "male_bodies", "male_actions")
GRIDS3 = ((0, 0, 8, 30), (0, 0, 8, 30), (2, 3, 32, 30), (1, 3, 17, 30)) * 2
VILLAGE_STOCK, THUNK_STOCK = bytes.fromhex("db44240853"), bytes.fromhex("8b09e9e9f3ffff")


class Draws3:
    """The Secret City with the DLL started and the engine's allocator and constructors stood in for."""

    def __init__(self, exe: bytes | None = None, start_as: int = 3):
        self.g = Game(3, exe if exe is not None else stock_exe(3), start=False, dll=DLL)
        p = self.p = self.g.p
        p.api_handlers["QueryPerformanceCounter"] = lambda p: (p.write(p.arg(0), struct.pack("<Q", 0x1234567)) or 1, 4)
        self.own = []
        for k in range(8):
            sheet = p.alloc(0x40)
            p.put32(VV3["slots"] + VV3["slot_at"][k], sheet)
            self.own.append(sheet)
        self.built, self.fail_load = [], False
        p.stub(VV3["alloc"], lambda p: (p.alloc(0x34), 0))
        p.stub(VV3["grid"], lambda p: self._construct(p, 6))
        p.stub(VV3["one"], lambda p: self._construct(p, 3))
        p.export("VvfpStartup", start_as, 0)
        self.images = p.exe_path.decode().rsplit("\\", 1)[0] + "\\Images\\"

    def _construct(self, p, count: int):
        obj = p.reg("ecx")
        args = [p.arg(i) for i in range(count)]
        name = p.cstring(args[0])
        self.built.append((name,) + ((p.cstring(args[1]),) + tuple(args[2:]) if count == 6 else tuple(args[1:])))
        p.put32(obj + 0x10, 0 if self.fail_load else 40)
        return obj, 4 * count

    def picture(self, tone: int, k: int, missing: int = -1) -> None:
        across, down, _, _ = GRIDS3[k]
        base = f"vvfp_skin_{tone:02d}_{SHEETS3[k]}"
        names = [f"{base}{a}{d}.png" for a in range(across) for d in range(down)] if across else [base]
        for n, name in enumerate(names):
            if n != missing:
                self.g.disk.files[(self.images + name).lower()] = b"png"

    def villager(self, tone: int, i: int = 3) -> int:
        record = self.g.villager(i, f"Keoni{i}", age=600)
        if tone:
            self.g.later()
            assert self.p.export("VvfpSkinToneSet", 3, record, tone) == 1
        return record

    def _enter(self, start: int, until: int, esi: int, sheet: int, ecx: int):
        p = self.p
        esp = STACK_TOP - 0x4000
        for i, value in enumerate((0x00C0FFEE, sheet, 120, 212, 9, 5, 0x3F800000)):
            p.put32(esp + 4 * i, value)
        regs = dict(esp=esp, esi=esi, ecx=ecx, eax=0x0A0A0A0A, edx=0x0D0D0D0D, ebx=0x11111111, edi=0x22222222,
                    ebp=0x33333333)
        for name, value in regs.items():
            p.set_reg(name, value)
        self.g.later()
        p.run(start, until)
        return esp, regs

    def village(self, record: int, sheet: int) -> int:
        """The village's draw entered for a villager; the sheet it then draws from."""
        p = self.p
        esp, regs = self._enter(VV3["village"], VV3["village"] + 5, record, sheet, VV3["renderer"])
        assert p.reg("esp") == esp - 4 and p.u32(esp - 4) == regs["ebx"], "the entry's own `push ebx` was not run once"
        for name in ("esi", "ecx", "eax", "edx", "ebx", "edi", "ebp"):
            assert p.reg(name) == regs[name], name
        assert [p.u32(esp + 4 * i) for i in (0, 2, 3, 4, 5, 6)] == [0x00C0FFEE, 120, 212, 9, 5, 0x3F800000]
        return p.u32(esp + 4)

    def thunk(self, esi: int, sheet: int) -> int:
        """The thunk entered (the Villager Details portrait, a figure, or the village's draw after it)."""
        p = self.p
        holder = p.alloc(8)
        p.put32(holder, 0x00ABCDEF)
        esp, regs = self._enter(VV3["thunk"], VV3["entry"], esi, sheet, holder)
        assert p.reg("esp") == esp and p.reg("ecx") == 0x00ABCDEF, "the thunk's own `mov ecx, [ecx]` was not run once"
        for name in ("esi", "eax", "edx", "ebx", "edi", "ebp"):
            assert p.reg(name) == regs[name], name
        return p.u32(esp + 4)


@unittest.skipUnless(HAVE_EMULATOR and have(3), "unicorn/pefile, the stock VV3 or the DLL is missing")
class TheSecretCity(unittest.TestCase):
    def test_the_sites_and_the_sheet_descriptions(self):
        pe = pefile.PE(data=stock_exe(3))
        image, base = pe.get_memory_mapped_image(), pe.OPTIONAL_HEADER.ImageBase
        self.assertEqual(image[VV3["village"] - base:VV3["village"] - base + 5], VILLAGE_STOCK)
        self.assertEqual(image[VV3["thunk"] - base:VV3["thunk"] - base + 7], THUNK_STOCK)
        for k, name in enumerate(SHEETS3):
            fields = struct.unpack_from("<8I", image, VV3["sheets"] + k * 0x30 - base)
            got = image[fields[1] - base:fields[1] - base + 32].split(b"\0")[0].decode()
            with self.subTest(sheet=name):
                self.assertEqual((fields[0], got, fields[5], fields[6], fields[2], fields[3]), (0x84 + k, name) + GRIDS3[k])
        # The loader 0x45C730 stores sheet 0x84 + k at manager + 0x127C20 + slot_at[k]: `mov [esi + disp32], eax`.
        loader = image[0x45C730 - base:0x45C730 - base + 0x110]
        for k, at in enumerate(VV3["slot_at"]):
            push = loader.index(b"\x68" + struct.pack("<I", 0x84 + k))
            store = loader.index(b"\x89\x86" + struct.pack("<I", 0x127C20 + at))
            self.assertLess(push, store, SHEETS3[k])

    def test_installs_both_sites(self):
        t = Draws3()
        self.assertEqual(t.p.export("VvfpSkinToneDrawn", 3), 1)
        self.assertEqual(t.p.read(VV3["village"], 1), b"\xE9")
        self.assertEqual(t.p.read(VV3["thunk"], 1) + t.p.read(VV3["thunk"] + 5, 2), b"\xE9\x90\x90")

    def test_all_or_nothing(self):
        for va, stock in ((VV3["village"], VILLAGE_STOCK), (VV3["thunk"], THUNK_STOCK)):
            for k in (0, len(stock) - 1):
                exe = bytearray(stock_exe(3))
                pe = pefile.PE(data=bytes(exe))
                exe[pe.get_offset_from_rva(va + k - 0x400000)] ^= 0xFF
                t = Draws3(bytes(exe))
                with self.subTest(site=hex(va), byte=k):
                    self.assertEqual(t.p.export("VvfpSkinToneDrawn", 3), 0)
                    other, other_stock = ((VV3["thunk"], THUNK_STOCK) if va == VV3["village"]
                                          else (VV3["village"], VILLAGE_STOCK))
                    self.assertEqual(t.p.read(other, len(other_stock)), other_stock)

    def test_another_game_installs_nothing(self):
        t = Draws3(start_as=2)
        self.assertEqual(t.p.export("VvfpSkinToneDrawn", 3), 0)
        self.assertEqual(t.p.read(VV3["village"], 5), VILLAGE_STOCK)
        self.assertEqual(t.p.read(VV3["thunk"], 7), THUNK_STOCK)

    def test_a_villager_with_a_tone_is_drawn_from_that_tones_sheet(self):
        t = Draws3()
        record = t.villager(7)
        for k in range(8):
            t.picture(7, k)
        for k in range(8):
            with self.subTest(sheet=SHEETS3[k]):
                in_village = t.village(record, t.own[k])
                self.assertNotIn(in_village, t.own)
                self.assertEqual(t.thunk(record, t.own[k]), in_village, "the Details portrait: the same sheet")
                # The village's draw goes on to the thunk with the renderer in ESI and the sheet already chosen.
                self.assertEqual(t.thunk(VV3["renderer"], in_village), in_village)
        expected = sorted((f"vvfp_skin_07_{SHEETS3[k]}",) + ((".png",) + GRIDS3[k] if GRIDS3[k][0] else GRIDS3[k][2:])
                          for k in range(8))
        self.assertEqual(sorted(t.built), expected, "each built once, by the game's own description")

    def test_the_games_own_sheet_otherwise(self):
        t = Draws3()
        toned, default = t.villager(4, 3), t.villager(GAMES_OWN, 4)
        t.picture(4, 4)                                             # only the men's young heads of tone 4
        t.picture(4, 6, missing=2)                                  # the men's bodies: one file short
        for tone in range(1, 11):
            t.picture(tone, 0)
        self.assertNotIn(t.village(toned, t.own[4]), t.own)
        self.assertEqual(t.village(toned, t.own[5]), t.own[5], "no picture of that sheet")
        self.assertEqual(t.village(toned, t.own[6]), t.own[6], "half a set")
        self.assertEqual(t.village(default, t.own[0]), t.own[0], "Default chosen")
        self.assertEqual(t.thunk(default, t.own[0]), t.own[0], "Default chosen")
        skeleton = t.p.alloc(0x40)
        self.assertEqual(t.village(toned, skeleton), skeleton, "a sheet that is not a villager's")
        self.assertEqual(t.thunk(VV3["renderer"], t.own[4]), t.own[4], "ESI is not a villager")
        self.assertEqual(t.village(t.g.record(40), t.own[4]), t.own[4], "a record nobody holds")

    def test_a_load_that_fails_keeps_the_games_own(self):
        t = Draws3()
        record = t.villager(5)
        t.picture(5, 4)
        t.fail_load = True
        self.assertEqual(t.village(record, t.own[4]), t.own[4])
        t.fail_load = False
        self.assertEqual(t.village(record, t.own[4]), t.own[4], "tried once, not again in this session")
        self.assertEqual(len(t.built), 1)

    def test_every_mode_with_every_patch(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                t = Draws3(rendered(3, mode))
                self.assertEqual(t.p.export("VvfpSkinToneDrawn", 3), 1)
                record = t.villager(8)
                t.picture(8, 0)
                self.assertNotIn(t.village(record, t.own[0]), t.own)
                self.assertNotIn(t.thunk(record, t.own[0]), t.own)
                self.assertEqual(t.village(record, t.own[2]), t.own[2])


@unittest.skipUnless(HAVE_EMULATOR and have(4), "unicorn/pefile, the stock VV4 or the DLL is missing")
class TheTreeOfLife(_Base, unittest.TestCase):
    GAME = 4


@unittest.skipUnless(HAVE_EMULATOR and have(5), "unicorn/pefile, the stock VV5 or the DLL is missing")
class NewBelievers(_Base, unittest.TestCase):
    GAME = 5


if __name__ == "__main__":
    unittest.main()
