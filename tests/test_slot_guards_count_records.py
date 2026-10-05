"""A New Home's and The Lost Children's villager-slot guards, RUN from the rendered executable.

Both games keep 256 villager records, and a corpse keeps its record until the
game removes it, so the living, the babies still owed and the corpses can
fill all 256 while the population is below the cap.  Their creators then have
no record to take: A New Home's walks off the end of the table (the owner's
Golden Child went to the 257th record, which no loop reads, while the mother's
pregnancy was spent), The Lost Children's stops at record 255 and takes it
over.  scripts/build_slot_guards.py has the whole story.

Every guard is executed here in an emulator, from the rendered executable's
own bytes, in every population mode, against a fake village whose records are
occupied (some of them corpses) to just below, at and above what the creation
needs:

  * a creation that fits reaches the game's creator with the STOCK return
    address (Cause of Death's arrival markers read it, cod_arrival_sites.inc)
    and the caller's arguments; one that does not fit never reaches it, and
    the game resumes where the stock code goes when there is nothing to make,
    with the stack balanced;
  * the Golden Child puzzle fires only with a free record, and with none it
    spends nothing: the mother keeps her pregnancy marker (+0x394);
  * twins and triplets at conception are decided by the occupied records,
    never by Babies Made (A New Home's old guard read that lifetime total,
    [world+0x9E24], so a village that had made 256 babies never had twins
    again), and never by the population counter (The Lost Children's old
    guards, which leave the corpses out).
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc, UcError
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDI,
    UC_X86_REG_EDX, UC_X86_REG_EFLAGS, UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vv_fun_patcher as vfp  # noqa: E402

STOCK = ROOT / "research" / "stock-executables"
EXE = {"vv1": "Virtual Villagers - A New Home.exe", "vv2": "Virtual Villagers - The Lost Children.exe"}
MODES = ("stock", "collection_progression", "immediate_fixed")

ARRAY = 0x10000000            # the villager array (record 0)
WORLD = 0x30000000            # the world object
OBJ = 0x31000000              # an event object / the delivery's village object
STACK = 0x32000000
STACK_TOP = STACK + 0x10000 - 0x100
SENTINEL = 0x0BADF00D         # a fake caller's return address, mapped so a ret can land on it

VV1 = dict(stride=0x3D8, flag=0x28, health=0x344, world_of_array=0x3E010)
VV2 = dict(stride=0xE48C, flag=0x30, health=0x4FC, world_of_array=0xE574D4, array_of_world=0x305A4)

_IMAGES: dict[tuple[str, str], tuple[bytes, int]] = {}


def image(game: str, mode: str) -> bytes:
    key = (game, mode)
    if key not in _IMAGES:
        build = next(b for b in vfp.load_builds() if b.id == game)
        data, _ = vfp.render_patched_bytes(STOCK / EXE[game], build, mode, [])
        pe = pefile.PE(data=bytes(data))
        _IMAGES[key] = (pe.get_memory_mapped_image(), pe.OPTIONAL_HEADER.ImageBase)
    return _IMAGES[key][0]


class Stop(Exception):
    pass


class Machine:
    """The rendered image, a fake village, and stops at the addresses given."""

    def __init__(self, game: str, mode: str, occupied: int, corpses: int = 0, babies_made: int = 0):
        self.game = game
        layout = VV1 if game == "vv1" else VV2
        self.layout = layout
        img = image(game, mode)
        self.uc = uc = Uc(UC_ARCH_X86, UC_MODE_32)
        size = (len(img) + 0xFFF) & ~0xFFF
        uc.mem_map(0x400000, size)
        uc.mem_write(0x400000, img)
        array_size = (257 * layout["stride"] + layout["world_of_array"] + 0x2000 + 0xFFF) & ~0xFFF
        uc.mem_map(ARRAY, array_size)
        uc.mem_map(WORLD, 0x40000)
        uc.mem_map(OBJ, 0x10000)
        uc.mem_map(STACK, 0x10000)
        uc.mem_map(SENTINEL & ~0xFFF, 0x1000)
        uc.mem_write(ARRAY + layout["world_of_array"], struct.pack("<I", WORLD))
        if game == "vv2":
            uc.mem_write(WORLD + layout["array_of_world"], struct.pack("<I", ARRAY))
        else:
            uc.mem_write(WORLD + 0x9E24, struct.pack("<I", babies_made))
        # The occupied records: the living first, then the corpses (health 0),
        # spread through the table so no guard can count only a prefix.
        order = list(range(0, 256, 2)) + list(range(1, 256, 2))
        for n, i in enumerate(order[:occupied]):
            rec = ARRAY + i * layout["stride"]
            uc.mem_write(rec + layout["flag"], b"\x01")
            uc.mem_write(rec + layout["health"], struct.pack("<i", 0 if n >= occupied - corpses else 90))
        self.stops: dict[int, str] = {}
        self.where = None
        uc.hook_add(UC_HOOK_CODE, self._hook)

    def _hook(self, uc, address, size, user):
        if address in self.stops:
            self.where = address
            uc.emu_stop()

    def reg(self, r):
        return self.uc.reg_read(r)

    def dword(self, va):
        return struct.unpack("<I", self.uc.mem_read(va, 4))[0]

    def run(self, start: int, stops: dict[int, str], regs: dict | None = None, stack: tuple = ()) -> str:
        self.stops = dict(stops)
        self.stops[SENTINEL] = "returned"
        esp = STACK_TOP - 4 * len(stack)
        for k, v in enumerate(stack):
            self.uc.mem_write(esp + 4 * k, struct.pack("<I", v & 0xFFFFFFFF))
        self.uc.reg_write(UC_X86_REG_ESP, esp)
        self.esp0 = esp
        for r, v in (regs or {}).items():
            self.uc.reg_write(r, v & 0xFFFFFFFF)
        self.where = None
        self.uc.emu_start(start, 0xFFFFFFFF, count=100000)
        if self.where is None:
            raise AssertionError(f"ran off from {start:#x}: eip {self.reg(UC_X86_REG_EIP):#x}")
        return self.stops[self.where]


def mother(game: str, index: int = 3) -> int:
    return ARRAY + index * (VV1 if game == "vv1" else VV2)["stride"]


class VV1Guards(unittest.TestCase):
    CREATE, COPY, ROOM = 0x43C350, 0x43C840, 0x43A1A0

    def each_mode(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                yield mode

    def test_the_golden_child_puzzle_needs_a_free_record_and_spends_nothing_without_one(self):
        for mode in self.each_mode():
            for occupied, fires in ((255, True), (256, False)):
                m = Machine("vv1", mode, occupied, corpses=9)
                mom = 3 * 0x3D8
                m.uc.mem_write(ARRAY + mom + 0x394, struct.pack("<I", 0x27))
                where = m.run(0x42427B, {0x424286: "puzzle", 0x4243AC: "not ready"},
                              {UC_X86_REG_ECX: ARRAY, UC_X86_REG_EDI: mom, UC_X86_REG_EBP: 3})
                self.assertEqual(where, "puzzle" if fires else "not ready", occupied)
                self.assertEqual(m.dword(ARRAY + mom + 0x394), 0xC7 if fires else 0x27,
                                 "the mother's marker is written only when the puzzle fires")
                self.assertEqual(m.reg(UC_X86_REG_ESP), m.esp0, "stack balanced")
                self.assertEqual(m.reg(UC_X86_REG_ECX), ARRAY, "ecx (the array) kept for the caller")

    def litter(self, mode, site, litter, occupied, babies_made=0):
        m = Machine("vv1", mode, occupied, corpses=7, babies_made=babies_made)
        rec = mother("vv1")
        cont = {0x43BC4E: 0x43BC58, 0x43BC8C: 0x43BC96}[site]
        back = {0x43BC4E: 0x43BC4C, 0x43BC8C: 0x43BC8A}[site]
        where = m.run(site, {cont: "kept", back: "refused"}, {UC_X86_REG_EDI: ARRAY, UC_X86_REG_ESI: rec})
        self.assertEqual(m.reg(UC_X86_REG_ESP), m.esp0)
        if where == "refused":
            flags = m.reg(UC_X86_REG_EFLAGS)
            sf, of = bool(flags & 0x80), bool(flags & 0x800)
            self.assertEqual(sf, of, "the roll's own jge is taken when the guard refuses")
            self.assertEqual(m.dword(rec + 0x35C), 0)
        else:
            self.assertEqual(m.dword(rec + 0x35C), litter)
        return where

    def test_twins_and_triplets_follow_the_records_not_babies_made(self):
        for mode in self.each_mode():
            self.assertEqual(self.litter(mode, 0x43BC4E, 2, 254), "kept")
            self.assertEqual(self.litter(mode, 0x43BC4E, 2, 255), "refused")
            self.assertEqual(self.litter(mode, 0x43BC8C, 3, 253), "kept")
            self.assertEqual(self.litter(mode, 0x43BC8C, 3, 254), "refused")
            # the owner's village: Babies Made far past 256, the records free
            self.assertEqual(self.litter(mode, 0x43BC4E, 2, 120, babies_made=315), "kept")
            self.assertEqual(self.litter(mode, 0x43BC8C, 3, 120, babies_made=315), "kept")

    def creation(self, mode, site, occupied, ret_expected, skip, args=5, creator=None):
        creator = creator or self.CREATE
        m = Machine("vv1", mode, occupied, corpses=5)
        stack = tuple(range(0x100, 0x100 + args))
        where = m.run(site, {creator: "created", skip: "skipped"},
                      {UC_X86_REG_ECX: ARRAY, UC_X86_REG_EBX: 77}, stack=stack)
        if where == "created":
            self.assertEqual(m.dword(m.reg(UC_X86_REG_ESP)), ret_expected, "the stock return address")
            self.assertEqual(m.reg(UC_X86_REG_ECX), ARRAY)
            if creator == self.COPY:
                self.assertEqual(m.dword(m.reg(UC_X86_REG_ESP) + 4), 77, "the copy's argument")
            else:
                self.assertEqual(m.reg(UC_X86_REG_ESP) + 4, m.esp0, "the caller's arguments in place")
        else:
            self.assertEqual(m.reg(UC_X86_REG_ESP), m.esp0 + 4 * args, "arguments dropped, stack balanced")
        return where

    def test_a_delivery_creates_only_into_a_free_record(self):
        for mode in self.each_mode():
            self.assertEqual(self.creation(mode, 0x42EFD0, 255, 0x42EFD5, 0x42F0A9), "created")
            self.assertEqual(self.creation(mode, 0x42EFD0, 256, 0x42EFD5, 0x42F0A9), "skipped")
            # the golden-child mother's extra child needs two records
            self.assertEqual(self.creation(mode, 0x42EF5F, 254, 0x42EF64, 0x42EF9B), "created")
            self.assertEqual(self.creation(mode, 0x42EF5F, 255, 0x42EF64, 0x42EF9B), "skipped")
            for site in (0x42F020, 0x42F06C):
                ret = site + 6
                self.assertEqual(self.creation(mode, site, 255, ret, 0x42F0A9, args=0, creator=self.COPY),
                                 "created")
                self.assertEqual(self.creation(mode, site, 256, ret, 0x42F0A9, args=0, creator=self.COPY),
                                 "skipped")

    def test_island_events_create_only_into_a_free_record(self):
        for mode in self.each_mode():
            for occupied, expect in ((255, "created"), (256, "returned")):
                m = Machine("vv1", mode, occupied, corpses=20)
                where = m.run(0x456680, {self.CREATE: "created"}, {UC_X86_REG_ECX: ARRAY},
                              stack=(SENTINEL, 1, 2, 3, 4, 5))
                self.assertEqual(where, expect)
                if where == "created":
                    self.assertEqual(m.dword(m.reg(UC_X86_REG_ESP)), SENTINEL, "the caller's return address")
                else:
                    self.assertEqual(m.reg(UC_X86_REG_EAX), 0xFFFFFFFF)
                    self.assertEqual(m.reg(UC_X86_REG_ESP), m.esp0 + 4 + 0x14, "ret 0x14")
            # every Barrel and crate call goes through it
            img = image("vv1", mode)
            for va in (0x428263, 0x4282C6, 0x4282E3, 0x42833C, 0x428359, 0x428376,
                       0x42C3EF, 0x42C410, 0x42C431, 0x42C4AF, 0x42C4D0, 0x42C54E):
                o = va - 0x400000
                self.assertEqual(img[o], 0xE8)
                self.assertEqual((va + 5 + struct.unpack_from("<i", img, o + 1)[0]) & 0xFFFFFFFF, 0x456680)

    def test_the_mysterious_face_asks_for_a_free_record(self):
        for mode in self.each_mode():
            for occupied, room, expect in ((255, 1, 1), (256, 1, 0), (10, 0, 0)):
                m = Machine("vv1", mode, occupied, corpses=3)
                # the game's room predicate, faked: al = room
                m.uc.mem_write(self.ROOM, bytes([0xB0, room, 0xC3]))
                where = m.run(0x419700, {0x419705: "back"}, {UC_X86_REG_ECX: ARRAY})
                self.assertEqual(where, "back")
                self.assertEqual(m.reg(UC_X86_REG_EAX) & 0xFF, expect, (occupied, room))


class VV2Guards(unittest.TestCase):
    EVENT, COPY, BIRTH, ROOM = 0x44F580, 0x44CEC0, 0x44F5C0, 0x44B310

    def each_mode(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                yield mode

    def litter(self, mode, site, litter, occupied, corpses):
        m = Machine("vv2", mode, occupied, corpses=corpses)
        rec = mother("vv2")
        cont = {0x44BA82: 0x44BA8C, 0x44BAB6: 0x44BAC0}[site]
        back = {0x44BA82: 0x44BA80, 0x44BAB6: 0x44BAB4}[site]
        where = m.run(site, {cont: "kept", back: "refused"}, {UC_X86_REG_EDI: ARRAY, UC_X86_REG_ESI: rec})
        self.assertEqual(m.reg(UC_X86_REG_ESP), m.esp0)
        self.assertEqual(m.dword(rec + 0x544), litter if where == "kept" else 0)
        return where

    def test_twins_and_triplets_count_the_corpses(self):
        for mode in self.each_mode():
            self.assertEqual(self.litter(mode, 0x44BA82, 2, 254, 30), "kept")
            # 225 living + 30 corpses: the population counter said 225 (room),
            # but only one record is free
            self.assertEqual(self.litter(mode, 0x44BA82, 2, 255, 30), "refused")
            self.assertEqual(self.litter(mode, 0x44BAB6, 3, 253, 30), "kept")
            self.assertEqual(self.litter(mode, 0x44BAB6, 3, 254, 30), "refused")

    def test_island_events_create_only_into_a_free_record(self):
        for mode in self.each_mode():
            for occupied, expect in ((255, "created"), (256, "returned")):
                m = Machine("vv2", mode, occupied, corpses=40)
                m.uc.mem_write(OBJ + 0x50A4, struct.pack("<I", WORLD))
                where = m.run(0x473D00, {self.EVENT: "created"}, {UC_X86_REG_EBP: OBJ, UC_X86_REG_ECX: ARRAY},
                              stack=(SENTINEL, 1, 2, 3, 4, 5))
                self.assertEqual(where, expect)
                if where == "created":
                    self.assertEqual(m.dword(m.reg(UC_X86_REG_ESP)), SENTINEL)
                    self.assertEqual(m.reg(UC_X86_REG_ECX), ARRAY)
                else:
                    self.assertEqual(m.reg(UC_X86_REG_EAX), 0xFFFFFFFF)
                    self.assertEqual(m.reg(UC_X86_REG_ESP), m.esp0 + 4 + 0x14)

    def test_a_delivery_waits_for_a_free_record(self):
        for mode in self.each_mode():
            for occupied, expect in ((255, "born"), (256, "deferred")):
                m = Machine("vv2", mode, occupied, corpses=50)
                m.uc.mem_write(OBJ, struct.pack("<II", WORLD, ARRAY))
                stack = tuple(range(0x200, 0x200 + 11))
                where = m.run(0x43BE8E, {self.BIRTH: "born", 0x43BF8C: "deferred"},
                              {UC_X86_REG_ESI: OBJ, UC_X86_REG_ECX: ARRAY}, stack=stack)
                self.assertEqual(where, expect)
                if where == "deferred":
                    self.assertEqual(m.reg(UC_X86_REG_ESP), m.esp0 + 0x2C)

    def test_a_delivery_s_twin_and_triplet_copies_need_a_free_record(self):
        for mode in self.each_mode():
            for site in (0x43BEDE, 0x43BF2A):
                for occupied, expect in ((255, "created"), (256, "skipped")):
                    m = Machine("vv2", mode, occupied, corpses=50)
                    m.uc.mem_write(OBJ, struct.pack("<II", WORLD, ARRAY))
                    where = m.run(site, {self.COPY: "created", 0x43BF67: "skipped"},
                                  {UC_X86_REG_ESI: OBJ, UC_X86_REG_ECX: ARRAY, UC_X86_REG_EBX: 9})
                    self.assertEqual(where, expect)
                    if where == "created":
                        self.assertEqual(m.dword(m.reg(UC_X86_REG_ESP)), site + 6, "stock return address")
                        self.assertEqual(m.dword(m.reg(UC_X86_REG_ESP) + 4), 9)
                        self.assertEqual(m.reg(UC_X86_REG_ECX), ARRAY)
                    else:
                        self.assertEqual(m.reg(UC_X86_REG_ESP), m.esp0)

    def test_the_silver_mirror_asks_for_a_free_record(self):
        for mode in self.each_mode():
            for occupied, room, expect in ((255, 1, 1), (256, 1, 0), (10, 0, 0)):
                m = Machine("vv2", mode, occupied, corpses=60)
                m.uc.mem_write(self.ROOM, bytes([0xB0, room, 0xC3]))
                where = m.run(0x4217DF, {0x4217E4: "back"}, {UC_X86_REG_ECX: ARRAY})
                self.assertEqual(where, "back")
                self.assertEqual(m.reg(UC_X86_REG_EAX) & 0xFF, expect, (occupied, room))
                self.assertEqual(m.reg(UC_X86_REG_ECX), ARRAY)


if __name__ == "__main__":
    unittest.main()
