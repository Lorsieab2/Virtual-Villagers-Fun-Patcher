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
set is missing, when the load fails, for a chosen Game's own, for a register that is no villager, and for a sheet that
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
            body_sites=(0x4681C7, 0x45F616, 0x45F917), not_sites=(0x43D00F, 0x43CF8C),
            carry_desc=0x4C37C8, carry_rows=6, carry_entry=0x466770, carry_item=0x1CDC, carry_draw=0x44C640,
            carry_args=3, carry_return=0x4680D7, detail=0x409AD0,
            detail_sites=(0x45F75E, 0x45F787, 0x45F7AF, 0x45FA4E, 0x45FA73, 0x45FA99)),
    5: dict(alloc=0x47BBDC, grid=0x40B0A0, one=0x40B010, sheets=0x4D1DA8, table=0x5258B8,
            head=0x451DA0, body=0x451D00, head_sites=(0x47233B, 0x466DB7, 0x4670CC),
            body_sites=(0x472683, 0x466D17, 0x467047), not_sites=(0x43F8DF, 0x43F85C),
            carry_desc=0x4D1A78, carry_rows=7, carry_entry=0x4701C0, carry_item=0x1D0C, carry_draw=0x44F380,
            carry_args=4, carry_return=0x472551, detail=0x409D00,
            detail_sites=(0x466E81, 0x466EAA, 0x466ED3, 0x46717E, 0x4671A3, 0x4671C9)),
}
CARRY_STOCK = bytes.fromhex("8b44240456")       # the carried-item draw's entry: mov eax, [esp+4]; push esi
CARRYING = 0x1C4C                               # pregnant or nursing (The Tree of Life and New Believers)
LITTER = 0x1C50
BABY = 3                                        # the baby's cell on carrying.png, and the carried item
CLOTH_SACKS_SITE = 0x4667B4                     # "VVFP Cloth Sacks.dll"'s: never ours
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
        self.own_carrying = p.alloc(0x40)       # carrying.png, as the registry holds it
        p.put32(self.d["carry_desc"] + 0x2C, self.own_carrying)
        self.manager = p.alloc(0x40)            # the sprite manager: +0x24 carrying.png, +0x28 the other items
        self.other_items = p.alloc(0x40)
        p.put32(self.manager + 0x24, self.own_carrying)
        p.put32(self.manager + 0x28, self.other_items)
        self.fetched, self.built, self.fail_load = [], [], False
        self.drawn = []
        self.next_sheet = self.own[3]
        p.stub(self.d["head"], lambda p: self._fetch(p, 5, 0x1C))
        p.stub(self.d["body"], lambda p: self._fetch(p, 6, 0x20))
        p.stub(self.d["carry_draw"], self._world_draw)
        p.stub(self.d["detail"], self._detail_draw)
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

    def _world_draw(self, p):
        """The world draw the carried item calls: thiscall(sheet, x, y, cell, alpha)."""
        self.drawn.append((p.arg(0), p.arg(3), p.u32(self.manager + 0x24), p.reg("ecx")))
        return 0, 0x14

    def _detail_draw(self, p):
        """The Details figures' draw: thiscall(sheet, x, y, cell, scale, 0)."""
        self.drawn.append((p.arg(0), p.arg(3), [p.arg(i) for i in range(1, 6)], p.reg("ecx")))
        return 0, 0x18

    def carrying_picture(self, tone: int) -> None:
        self.g.disk.files[(self.images + f"vvfp_skin_{tone:02d}_carrying.png").lower()] = b"png"

    def carrier(self, tone: int, i: int = 3, conceived: bool = True, carrying: int = 1, litter: int = 1):
        """A villager of `tone` holding the baby (the carried item 3); (record, the baby's tone kept at a
        conception, or 0 when `conceived` is False)."""
        record = self.villager(tone, i)
        p = self.p
        p.put32(record + CARRYING, carrying)
        p.put32(record + LITTER, litter)
        p.put32(record + self.d["carry_item"], BABY)
        held = 0
        if conceived:
            self.g.later()
            held = p.export("VvfpSkinToneConceived", self.game, record, 0)
            assert 1 <= held <= 10
        return record, held

    def carry(self, record: int, item: int | None = None) -> list:
        """The village's carried-item draw entered for `record`; (sheet, cell) of each of its draws."""
        p, d = self.p, self.d
        if item is not None:
            p.put32(record + d["carry_item"], item)
        esp = STACK_TOP - 0x4000
        args = [record, 120, 212, 0x3F800000][:d["carry_args"]]
        p.put32(esp, d["carry_return"])
        for i, value in enumerate(args):
            p.put32(esp + 4 + 4 * i, value)
        self.drawn.clear()
        self.g.later()
        for name, value in (("esp", esp), ("ecx", self.manager), ("esi", 0x11111111), ("ebx", 0x22222222),
                            ("edi", 0x33333333), ("ebp", 0x44444444)):
            p.set_reg(name, value)
        p.run(d["carry_entry"], d["carry_return"])
        assert p.reg("esp") == esp + 4 + 4 * len(args), "the draw's arguments were not popped once"
        assert (p.reg("esi"), p.reg("ebx"), p.reg("edi"), p.reg("ebp")) == (0x11111111, 0x22222222, 0x33333333,
                                                                          0x44444444)
        assert p.u32(self.manager + 0x24) == self.own_carrying, "the manager's carrying sheet was not put back"
        for sheet, _, then, ecx in self.drawn:
            assert ecx == 0x4DB9F8 if self.game == 4 else ecx == 0x521078
            assert then == sheet or sheet == self.other_items
        return [(sheet, cell) for sheet, cell, _, _ in self.drawn]

    def detail(self, site: int, record: int, sheet: int, cell: int = BABY) -> int:
        """A Details figure's `call` of the draw as the game reaches it; the sheet the draw then got."""
        p = self.p
        esp = STACK_TOP - 0x4000
        args = [sheet, 30, 40, cell, 0xC8, 0]
        for i, value in enumerate(args):
            p.put32(esp + 4 * i, value)
        self.drawn.clear()
        self.g.later()
        for name, value in (("esp", esp), ("esi", record), ("ecx", 0x0C0C0C0C), ("ebx", 0x11111111),
                            ("edi", 0x22222222), ("ebp", 0x33333333)):
            p.set_reg(name, value)
        p.run(site, site + 5)
        assert p.reg("esp") == esp + 0x18, "the draw's arguments were not popped once"
        assert (p.reg("esi"), p.reg("ebx"), p.reg("edi"), p.reg("ebp")) == (record, 0x11111111, 0x22222222, 0x33333333)
        assert len(self.drawn) == 1
        got, got_cell, rest, ecx = self.drawn[0]
        assert ecx == 0x0C0C0C0C and got_cell == cell and rest == args[1:], "the draw's own arguments changed"
        return got

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

    def all_sites(self):
        """Every site of the game: (va, its stock five bytes, the opcode written there)."""
        d = DRAWS[self.GAME]
        calls = self.sites() + [(va, d["detail"]) for va in d["detail_sites"]]
        return [(va, self.stock_call(va, target), b"\xE8") for va, target in calls] + [
            (d["carry_entry"], CARRY_STOCK, b"\xE9")]

    def test_the_sites_are_the_games_own_calls(self):
        pe = pefile.PE(data=stock_exe(self.GAME))
        image, base = pe.get_memory_mapped_image(), pe.OPTIONAL_HEADER.ImageBase
        d = DRAWS[self.GAME]
        for va, stock, _ in self.all_sites() + [(d["not_sites"][0], self.stock_call(d["not_sites"][0], d["head"]), 0),
                                                (d["not_sites"][1], self.stock_call(d["not_sites"][1], d["body"]), 0)]:
            with self.subTest(site=hex(va)):
                self.assertEqual(image[va - base:va - base + 5], stock)

    def test_the_carried_item_and_the_details_baby(self):
        """The carried-item draw reads the item at the record's carry field and draws an item below 0x50 (VV4
        0x46) from the manager's +0x24 sheet with the item as the cell, any twin or triplet again by the
        litter; each Details block is gated by the carrying field and draws cell 3 from the same sheet."""
        pe = pefile.PE(data=stock_exe(self.GAME))
        image, base = pe.get_memory_mapped_image(), pe.OPTIONAL_HEADER.ImageBase
        d = DRAWS[self.GAME]
        entry = image[d["carry_entry"] - base:d["carry_entry"] - base + 0xA0]
        self.assertEqual(entry[5:11], b"\x8b\xb0" + struct.pack("<I", d["carry_item"]), "mov esi, [eax + item]")
        self.assertEqual(entry.count(b"\x8b\x47\x24") + entry.count(b"\x8b\x57\x24") + entry.count(b"\x8b\x4f\x24"), 3,
                         "three reads of the manager's +0x24 sheet")
        self.assertEqual(entry.count(b"\x83\xb9" + struct.pack("<I", LITTER)) + entry.count(b"\x83\xb8" + struct.pack("<I", LITTER)), 2)
        global_sheet = {4: 0x50E58C, 5: 0x55416C}[self.GAME]
        for va in d["detail_sites"]:
            block = image[va - base - 0x30:va - base]
            with self.subTest(site=hex(va)):
                self.assertIn(b"\x6a\x03", block, "cell 3")
                self.assertIn(struct.pack("<I", global_sheet), block, "the manager's carrying sheet")
        # carrying.png's description: one file, 13 columns.
        fields = struct.unpack_from("<12I", image, d["carry_desc"] - base)
        name = image[fields[1] - base:fields[1] - base + 16].split(b"\0")[0]
        self.assertEqual((name, fields[2], fields[3], fields[5]), (b"carrying.png", 13, d["carry_rows"], 0))

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
        for va, stock, opcode in self.all_sites():
            with self.subTest(site=hex(va)):
                now = t.p.read(va, 5)
                self.assertEqual(now[:1], opcode)
                self.assertNotEqual(now, stock)
        for va, target in zip(DRAWS[self.GAME]["not_sites"], (DRAWS[self.GAME]["head"], DRAWS[self.GAME]["body"])):
            self.assertEqual(t.p.read(va, 5), self.stock_call(va, target), "the memorial list is left alone")
        if self.GAME == 4:
            self.assertEqual(t.p.read(CLOTH_SACKS_SITE, 5), self.stock_call(CLOTH_SACKS_SITE, DRAWS[4]["carry_draw"]),
                             "the Cloth Sacks' carried-item call is left alone")

    def test_all_or_nothing(self):
        for va, _, _ in self.all_sites():
            for k in (0, 4):
                exe = bytearray(stock_exe(self.GAME))
                pe = pefile.PE(data=bytes(exe))
                exe[pe.get_offset_from_rva(va + k - 0x400000)] ^= 0xFF
                t = Draws(self.GAME, bytes(exe))
                with self.subTest(site=hex(va), byte=k):
                    self.assertEqual(t.p.export("VvfpSkinToneDrawn", self.GAME), 0)
                    for other, stock, _ in self.all_sites():
                        if other != va:
                            self.assertEqual(t.p.read(other, 5), stock)

    def test_another_game_installs_nothing(self):
        t = Draws(self.GAME, start=False)
        t.p.export("VvfpStartup", 3, 0)
        self.assertEqual(t.p.export("VvfpSkinToneDrawn", self.GAME), 0)
        for va, stock, _ in self.all_sites():
            self.assertEqual(t.p.read(va, 5), stock)

    # ---- the held baby ----------------------------------------------------------------------------

    def test_the_held_baby_is_drawn_in_its_own_tone_in_the_village(self):
        t = Draws(self.GAME)
        for tone in range(1, 11):
            t.carrying_picture(tone)
        record, held = t.carrier(2, litter=3)
        drawn = t.carry(record)
        self.assertEqual(len(drawn), 3, "the baby and two more of the litter")
        sheets = {sheet for sheet, _ in drawn}
        self.assertEqual(len(sheets), 1, "triplets are alike")
        self.assertNotIn(t.own_carrying, sheets)
        self.assertEqual([cell for _, cell in drawn], [BABY] * 3)
        self.assertEqual(t.built, [(f"vvfp_skin_{held:02d}_carrying.png", 13, DRAWS[self.GAME]["carry_rows"])],
                         "the baby's own tone (not the carrier's), built once by the game's own description")
        self.assertEqual(t.carry(record), drawn, "the same sheet every time")
        self.assertEqual(len(t.built), 1)

    def test_the_held_baby_is_drawn_in_its_own_tone_in_the_details(self):
        t = Draws(self.GAME)
        for tone in range(1, 11):
            t.carrying_picture(tone)
        record, held = t.carrier(9)
        seen = set()
        for site in DRAWS[self.GAME]["detail_sites"]:
            with self.subTest(site=hex(site)):
                got = t.detail(site, record, t.own_carrying)
                self.assertNotEqual(got, t.own_carrying)
                seen.add(got)
                other = t.p.alloc(0x40)
                self.assertEqual(t.detail(site, record, other), other, "a sheet that is not carrying.png")
                self.assertEqual(t.detail(site, record, t.own_carrying, cell=4), t.own_carrying, "a cell that is no baby")
        self.assertEqual(len(seen), 1)
        self.assertEqual(t.built, [(f"vvfp_skin_{held:02d}_carrying.png", 13, DRAWS[self.GAME]["carry_rows"])])
        village = t.carry(record)
        self.assertEqual(village[0][0], seen.pop(), "the village and the Details: the same baby")

    def test_the_held_baby_is_chosen_on_first_sight(self):
        t = Draws(self.GAME)
        for tone in range(1, 11):
            t.carrying_picture(tone)
        record, _ = t.carrier(6, conceived=False, litter=2)
        self.assertEqual(t.p.export("VvfpSkinTonePending", self.GAME, record), 0)
        drawn = t.carry(record)
        held = t.p.export("VvfpSkinTonePending", self.GAME, record)
        self.assertTrue(1 <= held <= 10, "chosen and kept")
        self.assertEqual(len({sheet for sheet, _ in drawn}), 1, "twins are alike")
        self.assertEqual(t.built, [(f"vvfp_skin_{held:02d}_carrying.png", 13, DRAWS[self.GAME]["carry_rows"])])
        self.assertEqual(t.p.export("VvfpSkinToneGet", self.GAME, record), 6, "the carrier's own tone is untouched")
        self.assertEqual(t.carry(record), drawn)
        self.assertEqual(t.p.export("VvfpSkinTonePending", self.GAME, record), held, "chosen once")

    def test_the_games_own_carrying_otherwise(self):
        t = Draws(self.GAME)
        record, held = t.carrier(4)
        self.assertEqual(t.carry(record), [(t.own_carrying, BABY)], "no picture of the baby's tone")
        self.assertEqual(t.detail(DRAWS[self.GAME]["detail_sites"][0], record, t.own_carrying), t.own_carrying)
        t2 = Draws(self.GAME)
        for tone in range(1, 11):
            t2.carrying_picture(tone)
        fruit, _ = t2.carrier(5, i=4, conceived=False, carrying=0)
        self.assertEqual(t2.carry(fruit, item=7), [(t2.own_carrying, 7)], "a carried item that is no baby")
        self.assertEqual(t2.carry(fruit, item=BABY), [(t2.own_carrying, BABY)],
                         "item 3 with no baby's tone kept and nobody pregnant or nursing: nothing is chosen")
        self.assertEqual(t2.p.export("VvfpSkinTonePending", self.GAME, fruit), 0)
        item = 0x50 if self.GAME == 5 else 0x46
        self.assertEqual(t2.carry(fruit, item=item), [(t2.other_items, 0)], "the other items' sheet")
        nobody = t2.g.record(40)
        t2.p.put32(nobody + DRAWS[self.GAME]["carry_item"], BABY)
        t2.p.put32(nobody + CARRYING, 1)
        self.assertEqual(t2.carry(nobody), [(t2.own_carrying, BABY)], "a record nobody holds")
        self.assertEqual(t2.built, [])

    def test_a_carrying_load_that_fails_keeps_the_games_own(self):
        t = Draws(self.GAME)
        for tone in range(1, 11):
            t.carrying_picture(tone)
        record, _ = t.carrier(3)
        t.fail_load = True
        self.assertEqual(t.carry(record), [(t.own_carrying, BABY)])
        t.fail_load = False
        self.assertEqual(t.carry(record), [(t.own_carrying, BABY)], "tried once, not again in this session")
        self.assertEqual(len(t.built), 1)

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

    def test_games_own_chosen_and_no_villager_and_other_sheets_are_the_games_own(self):
        t = Draws(self.GAME)
        record = t.villager(GAMES_OWN)
        for k in range(8):
            for tone in range(1, 11):
                t.picture(tone, k)
        head, body = DRAWS[self.GAME]["head_sites"][0], DRAWS[self.GAME]["body_sites"][0]
        self.assertEqual(t.draw(head, record, t.own[3]), t.own[3], "Game's own chosen")
        self.assertEqual(t.draw(body, record, t.own[4]), t.own[4], "Game's own chosen")
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
                for tone in range(1, 11):
                    t.carrying_picture(tone)
                carrier, _ = t.carrier(5, i=5)
                self.assertNotEqual(t.carry(carrier)[0][0], t.own_carrying)
                self.assertNotEqual(t.detail(d["detail_sites"][3], carrier, t.own_carrying), t.own_carrying)


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
        toned, own = t.villager(4, 3), t.villager(GAMES_OWN, 4)
        t.picture(4, 4)                                             # only the men's young heads of tone 4
        t.picture(4, 6, missing=2)                                  # the men's bodies: one file short
        for tone in range(1, 11):
            t.picture(tone, 0)
        self.assertNotIn(t.village(toned, t.own[4]), t.own)
        self.assertEqual(t.village(toned, t.own[5]), t.own[5], "no picture of that sheet")
        self.assertEqual(t.village(toned, t.own[6]), t.own[6], "half a set")
        self.assertEqual(t.village(own, t.own[0]), t.own[0], "Game's own chosen")
        self.assertEqual(t.thunk(own, t.own[0]), t.own[0], "Game's own chosen")
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
