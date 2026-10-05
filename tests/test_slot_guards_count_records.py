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
HAVE_STOCK = all((STOCK / name).is_file() for name in (
    "Virtual Villagers - A New Home.exe", "Virtual Villagers - The Lost Children.exe",
    "Virtual Villagers - The Secret City.exe", "Virtual Villagers - The Tree of Life.exe",
    "Virtual Villagers - New Believers.exe"))
needs_stock = unittest.skipUnless(HAVE_STOCK, "the stock executables are not in this checkout (research/ is git-ignored)")

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


@needs_stock
class VV1Guards(unittest.TestCase):
    CREATE, ROOM = 0x43C350, 0x43A1A0

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

    def delivery(self, mode, site, occupied, litter):
        """The delivery's creation at `site` with the mother's litter field
        (+0x35C: 0 one baby, 2 twins, 3 triplets): created with the stock
        return address and the caller's arguments, or the delivery waits --
        its arguments dropped, the tick going on at 0x42F0CE, the pregnancy
        kept (never 0x42F0A9, where it is cleared)."""
        m = Machine("vv1", mode, occupied, corpses=5)
        mom = 3 * 0x3D8
        m.uc.mem_write(ARRAY + mom + 0x35C, struct.pack("<I", litter))
        stack = tuple(range(0x100, 0x105))
        where = m.run(site, {self.CREATE: "created", 0x42F0CE: "waits", 0x42F0A9: "pregnancy cleared"},
                      {UC_X86_REG_ECX: ARRAY, UC_X86_REG_EDI: mom}, stack=stack)
        if where == "created":
            self.assertEqual(m.dword(m.reg(UC_X86_REG_ESP)), site + 5, "the stock return address")
            self.assertEqual(m.reg(UC_X86_REG_ECX), ARRAY)
            self.assertEqual(m.reg(UC_X86_REG_ESP) + 4, m.esp0, "the caller's arguments in place")
        elif where == "waits":
            self.assertEqual(m.reg(UC_X86_REG_ESP), m.esp0 + 0x14, "arguments dropped, stack balanced")
        return where

    def test_a_delivery_waits_until_its_whole_litter_fits(self):
        for mode in self.each_mode():
            for litter, babies in ((0, 1), (2, 2), (3, 3)):
                fits = 256 - babies
                self.assertEqual(self.delivery(mode, 0x42EFD0, fits, litter), "created", litter)
                self.assertEqual(self.delivery(mode, 0x42EFD0, fits + 1, litter), "waits", litter)
                # the golden-child mother's delivery: her Golden Child too
                self.assertEqual(self.delivery(mode, 0x42EF5F, fits - 1, litter), "created", litter)
                self.assertEqual(self.delivery(mode, 0x42EF5F, fits, litter), "waits", litter)

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


@needs_stock
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

    def test_a_delivery_waits_until_its_whole_litter_fits(self):
        for mode in self.each_mode():
            for litter, babies in ((0, 1), (2, 2), (3, 3)):
                for occupied, expect in ((256 - babies, "born"), (257 - babies, "waits")):
                    m = Machine("vv2", mode, occupied, corpses=50)
                    m.uc.mem_write(OBJ, struct.pack("<II", WORLD, ARRAY))
                    mom = 3 * 0xE48C
                    m.uc.mem_write(ARRAY + mom + 0x544, struct.pack("<I", litter))
                    stack = tuple(range(0x200, 0x200 + 11))
                    where = m.run(0x43BE8E, {self.BIRTH: "born", 0x43BF8C: "waits", 0x43BF67: "cleared"},
                                  {UC_X86_REG_ESI: OBJ, UC_X86_REG_ECX: ARRAY, UC_X86_REG_EDI: mom},
                                  stack=stack)
                    self.assertEqual(where, expect, (litter, occupied))
                    if where == "waits":
                        self.assertEqual(m.reg(UC_X86_REG_ESP), m.esp0 + 0x2C)
                    else:
                        self.assertEqual(m.reg(UC_X86_REG_EDI), mom, "registers restored")

    def test_the_strange_request_and_the_savage_child_are_offered_only_with_a_free_record(self):
        # The two-choice event chooser (0x41F570) runs the rolled event's
        # condition through its jump table at 0x41F5B2 and keeps it when bl
        # is set at 0x41F696.  Event 3, The Strange Request, was always
        # offered and its stranger took record 255 from a villager when every
        # record was occupied; event 4, The Savage Child, asked the room
        # predicate only.
        for mode in self.each_mode():
            for event, occupied, room, expect in ((3, 255, 1, 1), (3, 256, 1, 0),
                                                 (4, 255, 1, 1), (4, 256, 1, 0), (4, 10, 0, 0)):
                m = Machine("vv2", mode, occupied, corpses=70)
                m.uc.mem_write(self.ROOM, bytes([0xB0, room, 0xC3]))
                m.uc.mem_write(OBJ + 0x50AC, struct.pack("<I", WORLD))
                m.uc.mem_write(OBJ + 0x50B0, struct.pack("<I", ARRAY))
                where = m.run(0x41F5B2, {0x41F696: "chosen"},
                              {UC_X86_REG_EAX: event, UC_X86_REG_ESI: OBJ, UC_X86_REG_EBX: 0x5A5A5A00,
                               UC_X86_REG_EBP: 2})
                self.assertEqual(where, "chosen")
                self.assertEqual(m.reg(UC_X86_REG_EBX) & 0xFF, expect, (event, occupied, room))
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


@needs_stock
class VV4OriginsBarrel(unittest.TestCase):
    """The Tree of Life's Origins Barrel (scripts/build_vv4_origins_feature.py):
    its purchase gate (0x728C00, three children) and its checks before the
    second and third child (0x728B40 / 0x728B60, the purchased-barrel flag
    set) count the records' demand -- every occupied record, corpses and
    ghosts included, plus each pregnant mother's babies -- with the slot
    layer's counter 0x4890F0, never the population counter 0x467610, which
    skips corpses: the purchase could be charged and deliver nothing, or its
    children take the records pending babies need.  Run in the render with
    every public VV4 patch, both table sizes."""

    TABLE = {150: 0x50E5AC, 256: 0x800044}
    STRIDE = 0x2E3C

    def render(self, extra):
        build = next(b for b in vfp.load_builds() if b.id == "vv4")
        feats = [f.id for f in vfp.load_public_fun_patches()
                 if f.raw.get("game_id") == "vv4" and f.id != "vv4_population_256"] + extra
        data, _ = vfp.render_patched_bytes(STOCK / "Virtual Villagers - The Tree of Life.exe", build,
                                           "immediate_fixed", feats)
        return pefile.PE(data=bytes(data))

    def machine(self, pe, slots, living, corpses, pending):
        uc = Uc(UC_ARCH_X86, UC_MODE_32)
        for section in pe.sections:
            va = 0x400000 + section.VirtualAddress
            size = (max(section.Misc_VirtualSize, section.SizeOfRawData) + 0xFFF) & ~0xFFF
            uc.mem_map(va, size)
            uc.mem_write(va, section.get_data()[:size])
        uc.mem_map(STACK, 0x10000)
        uc.mem_map(SENTINEL & ~0xFFF, 0x1000)
        table = self.TABLE[slots]
        for i in range(living + corpses):
            rec = table + i * self.STRIDE
            uc.mem_write(rec + 0x1CC4, b"\x01")
            uc.mem_write(rec + 0x1C40, struct.pack("<i", 50 if i < living else 0))
        for i in range(pending):
            rec = table + i * self.STRIDE
            uc.mem_write(rec + 0x1C4C, struct.pack("<I", 300))
            uc.mem_write(rec + 0x1C50, struct.pack("<I", 1))
        return uc

    def call(self, uc, va):
        uc.reg_write(UC_X86_REG_ESP, STACK_TOP)
        uc.mem_write(STACK_TOP, struct.pack("<I", SENTINEL))
        uc.emu_start(va, SENTINEL, count=200000)
        return uc.reg_read(UC_X86_REG_EAX)

    def test_the_purchase_and_its_children_count_corpses_and_pending_babies(self):
        for slots, extra in ((150, []), (256, ["vv4_population_256"])):
            pe = self.render(extra)
            n = slots - 150
            with self.subTest(slots=slots):
                # 140 living, 7 corpses, 2 babies owed: the population says
                # 142 (three more fit), but 149 records are in demand.
                uc = self.machine(pe, slots, 140 + n, 7, 2)
                self.assertEqual(self.call(uc, 0x728C00), 0, "the purchase is refused, nothing charged")
                uc = self.machine(pe, slots, 138 + n, 7, 2)   # 147 in demand: three fit
                self.assertEqual(self.call(uc, 0x728C00), 1)
                # the second and third child of a purchased barrel
                for va in (0x728B40, 0x728B60):
                    uc = self.machine(pe, slots, 140 + n, 8, 2)   # 150 in demand
                    uc.mem_write(0x728B00, b"\x01")
                    self.assertEqual(self.call(uc, va) & 0xFF, 0, f"{va:#x}: no record left for it")
                    uc = self.machine(pe, slots, 139 + n, 8, 2)   # 149 in demand
                    uc.mem_write(0x728B00, b"\x01")
                    self.assertEqual(self.call(uc, va) & 0xFF, 1, f"{va:#x}")


@needs_stock
class VV3OriginsBarrelRecordCheck(unittest.TestCase):
    """The Secret City's Origins Barrel row and purchase preflight
    (native/vv3_full_mastery_candidate, vv3_has_free_villager_slots) ask
    whether three villagers fit in the records.  The active flag is ONE byte
    (the allocator 0x45F0C0 tests `byte [rec+0xF10]`); read as a dword it took
    in +0xF11..+0xF13, which freed records keep, so free records counted as
    taken.  And the babies pregnant mothers still owe (+0xE8C pregnant, +0xE90
    the litter) hold records too: uncounted, the barrel could take them and
    those pregnancies ended with no child at delivery."""

    SOURCE = ROOT / "native" / "vv3_full_mastery_candidate" / "vv3_full_mastery_candidate.c"

    def body(self):
        text = self.SOURCE.read_text(encoding="utf-8")
        head = "static int vv3_has_free_villager_slots(int wanted) {"
        start = text.index(head)
        return text[start:text.index("\n}\n", start)]

    def test_the_active_flag_is_read_as_a_byte(self):
        body = self.body()
        self.assertIn("*(volatile unsigned char *)(record + VV3_OFF_ACTIVE)", body)
        self.assertNotIn("*(volatile int *)(record + VV3_OFF_ACTIVE)", body)

    def test_pending_babies_take_records(self):
        body = self.body()
        self.assertIn("VV3_OFF_PREGNANT", body)
        self.assertIn("demand += *(volatile int *)(record + VV3_OFF_LITTER)", body)
        self.assertIn("return demand + wanted <= (int)bound;", body)


@needs_stock
class VV4VV5LitterGuards(unittest.TestCase):
    """The Tree of Life's and New Believers' twin and triplet guards ask the
    demand counter (occupied records plus every pregnant mother's babies),
    which already counts the conceiving mother's first baby: the conception
    writes +0x1C4C and +0x1C50 = 1 before the guard.  Triplets therefore need
    demand + 2 <= slots and twins demand + 1 <= slots; the guards had one more
    to spare (> 0x93 / > 0x94), so the last record never took a second or
    third baby.  Both table sizes."""

    GAMES = {
        "vv4": dict(exe="Virtual Villagers - The Tree of Life.exe", table={150: 0x50E5AC, 256: 0x800044},
                    stride=0x2E3C, active=0x1CC4, triplets=0x489020, twins=0x489040,
                    trip_kept=0x45E8CA, trip_refused=0x45E8D3, twin_kept=0x45E8DD, twin_refused=0x45E8E4),
        "vv5": dict(exe="Virtual Villagers - New Believers.exe", table={150: 0x554190, 256: 0x800048},
                    stride=0x2F44, active=0x1CD4, triplets=0x494340, twins=0x494360,
                    trip_kept=0x465F1A, trip_refused=0x465F23, twin_kept=0x465F2D, twin_refused=0x465F34),
    }

    def render(self, game, extra):
        build = next(b for b in vfp.load_builds() if b.id == game)
        data, _ = vfp.render_patched_bytes(STOCK / self.GAMES[game]["exe"], build, "immediate_fixed", extra)
        return pefile.PE(data=bytes(data))

    def run_guard(self, pe, game, slots, demand, va, stops):
        g = self.GAMES[game]
        uc = Uc(UC_ARCH_X86, UC_MODE_32)
        for section in pe.sections:
            base = 0x400000 + section.VirtualAddress
            size = (max(section.Misc_VirtualSize, section.SizeOfRawData) + 0xFFF) & ~0xFFF
            uc.mem_map(base, size)
            uc.mem_write(base, section.get_data()[:size])
        uc.mem_map(STACK, 0x10000)
        table = g["table"][slots]
        for i in range(demand):          # each record occupied, none pregnant but the mother
            uc.mem_write(table + i * g["stride"] + g["active"], b"\x01")
        mother = table + (demand - 1) * g["stride"]     # her record counts 1, her baby 1 more
        uc.mem_write(table + (demand - 2) * g["stride"] + g["active"], b"\x00")
        uc.mem_write(mother + 0x1C4C, struct.pack("<I", 300))
        uc.mem_write(mother + 0x1C50, struct.pack("<I", 1))
        hit = []

        def hook(u, address, size, user):
            if address in stops:
                hit.append(stops[address])
                u.emu_stop()
        uc.hook_add(UC_HOOK_CODE, hook)
        uc.reg_write(UC_X86_REG_ESP, STACK_TOP)
        uc.reg_write(UC_X86_REG_ESI, mother)
        uc.emu_start(va, 0xFFFFFFFF, count=100000)
        return hit[0]

    def test_the_last_records_take_the_extra_babies(self):
        for game, g in self.GAMES.items():
            for slots, extra in ((150, []), (256, [f"{game}_population_256"])):
                pe = self.render(game, extra)
                with self.subTest(game=game, slots=slots):
                    trip = {g["trip_kept"]: "kept", g["trip_refused"]: "refused"}
                    twin = {g["twin_kept"]: "kept", g["twin_refused"]: "refused"}
                    self.assertEqual(self.run_guard(pe, game, slots, slots - 2, g["triplets"], trip), "kept")
                    self.assertEqual(self.run_guard(pe, game, slots, slots - 1, g["triplets"], trip), "refused")
                    self.assertEqual(self.run_guard(pe, game, slots, slots - 1, g["twins"], twin), "kept")
                    self.assertEqual(self.run_guard(pe, game, slots, slots, g["twins"], twin), "refused")


# ---- The Secret City, The Tree of Life, New Believers ----------------------------
# scripts/build_record_guards_vv345.py.  Each guard runs from the image the
# patcher renders with every public patch, in stock mode and Immediate Fixed,
# with and without 256 Villagers.

VV345 = {
    "vv3": dict(exe="Virtual Villagers - The Secret City.exe", base={150: 0x59E124, 256: 0x800014},
                manager={150: 0x59E110, 256: 0x800000}, stride=0x1F8C, active=0xF10, health=0xE78,
                pregnant=0xE8C, litter=0xE90, delivery=0x460341, delivery_len=14, wait=0x460512,
                pregnant_rel=0xC0),
    "vv4": dict(exe="Virtual Villagers - The Tree of Life.exe", base={150: 0x50E5AC, 256: 0x800044},
                manager={150: 0x50E568, 256: 0x800000}, stride=0x2E3C, active=0x1CC4, health=0x1C40,
                pregnant=0x1C4C, litter=0x1C50, delivery=0x4687E4, delivery_len=11, wait=0x468A1A,
                pregnant_rel=0x10),
    "vv5": dict(exe="Virtual Villagers - New Believers.exe", base={150: 0x554190, 256: 0x800048},
                manager={150: 0x554148, 256: 0x800000}, stride=0x2F44, active=0x1CD4, health=0x1C40,
                pregnant=0x1C4C, litter=0x1C50, delivery=0x4730AF, delivery_len=11, wait=0x4732E1,
                pregnant_rel=0x10),
}
_RENDERS: dict = {}


def render345(game, mode, slots):
    key = (game, mode, slots)
    if key not in _RENDERS:
        build = next(b for b in vfp.load_builds() if b.id == game)
        feats = [f.id for f in vfp.load_public_fun_patches()
                 if f.raw.get("game_id") == game and not f.id.endswith("population_256")]
        if slots == 256:
            feats.append(f"{game}_population_256")
        data, _ = vfp.render_patched_bytes(STOCK / VV345[game]["exe"], build, mode, feats)
        _RENDERS[key] = pefile.PE(data=bytes(data))
    return _RENDERS[key]


class Village345:
    def __init__(self, game, mode, slots, occupied, corpses=0, pending=()):
        g = self.g = VV345[game]
        self.slots = slots
        pe = render345(game, mode, slots)
        self.uc = uc = Uc(UC_ARCH_X86, UC_MODE_32)
        for section in pe.sections:
            va = 0x400000 + section.VirtualAddress
            size = (max(section.Misc_VirtualSize, section.SizeOfRawData) + 0xFFF) & ~0xFFF
            uc.mem_map(va, size)
            uc.mem_write(va, section.get_data()[:size])
        uc.mem_map(STACK, 0x10000)
        uc.mem_map(SENTINEL & ~0xFFF, 0x1000)
        uc.mem_map(OBJ, 0x10000)
        self.base = g["base"][slots]
        for i in range(occupied):
            r = self.rec(i)
            uc.mem_write(r + g["active"], b"\x01")
            uc.mem_write(r + g["health"], struct.pack("<i", 0 if i >= occupied - corpses else 60))
        for i, babies in pending:
            uc.mem_write(self.rec(i) + g["pregnant"], struct.pack("<I", 300))
            uc.mem_write(self.rec(i) + g["litter"], struct.pack("<I", babies))
        self.stops = {}
        self.where = None
        uc.hook_add(UC_HOOK_CODE, self._hook)

    def rec(self, i):
        return self.base + i * self.g["stride"]

    def _hook(self, uc, address, size, user):
        if address in self.stops:
            self.where = self.stops[address]
            uc.emu_stop()

    def run(self, start, stops, regs=None, stack=()):
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
        self.uc.emu_start(start, 0xFFFFFFFF, count=400000)
        return self.where

    def reg(self, r):
        return self.uc.reg_read(r)

    def dword(self, va):
        return struct.unpack("<I", self.uc.mem_read(va, 4))[0]


def each345(test, games=("vv3", "vv4", "vv5")):
    for game in games:
        for mode in ("stock", "immediate_fixed"):
            for slots in (150, 256):
                with test.subTest(game=game, mode=mode, slots=slots):
                    yield game, mode, slots


@needs_stock
class VV345RecordGuards(unittest.TestCase):
    def test_a_delivery_waits_until_its_whole_litter_fits(self):
        for game, mode, slots in each345(self):
            g = VV345[game]
            for babies in (1, 2, 3):
                for occupied, expect in ((slots - babies, "delivers"), (slots - babies + 1, "waits")):
                    # the mother is the first record, her babies owed; corpses fill the rest
                    v = Village345(game, mode, slots, occupied, corpses=occupied // 3, pending=[(0, babies)])
                    mother = v.rec(0)
                    esi = mother + g["pregnant"] - g["pregnant_rel"]
                    where = v.run(g["delivery"], {g["delivery"] + g["delivery_len"]: "delivers",
                                                  g["wait"]: "waits"}, {UC_X86_REG_ESI: esi})
                    self.assertEqual(where, expect, (babies, occupied))
                    self.assertEqual(v.reg(UC_X86_REG_ESP), v.esp0)
                    self.assertEqual(v.dword(mother + g["pregnant"]), 300, "the pregnancy is kept")
                    if where == "delivers":
                        self.assertEqual(v.reg(UC_X86_REG_EAX), 300, "eax as the stock code left it")
            # not pregnant: no delivery, as before
            v = Village345(game, mode, slots, 10)
            where = v.run(g["delivery"], {g["delivery"] + g["delivery_len"]: "delivers", g["wait"]: "waits"},
                          {UC_X86_REG_ESI: v.rec(0) + g["pregnant"] - g["pregnant_rel"]})
            self.assertEqual(where, "waits")

    ROOM = {"vv3": (0x45FE37, 0x45E8F0), "vv4": (0x468357, 0x467610), "vv5": (0x472BD7, 0x4713F0)}

    def test_the_room_predicate_counts_corpses_and_babies_owed(self):
        for game, mode, slots in each345(self):
            site, population = self.ROOM[game]
            for occupied, pending, full in ((slots - 3, [(0, 2)], False), (slots - 3, [(0, 2), (1, 1)], True),
                                            (slots, [], True), (slots - 1, [], False)):
                v = Village345(game, mode, slots, occupied, corpses=occupied // 2, pending=pending)
                # the stock population count, stubbed to a small village
                v.uc.mem_write(population, bytes([0xB8, 7, 0, 0, 0, 0xC3]))
                where = v.run(site, {site + 5: "back"}, {UC_X86_REG_ECX: VV345[game]["manager"][slots]})
                self.assertEqual(where, "back")
                self.assertEqual(v.reg(UC_X86_REG_EAX), 0x7FFF if full else 7, (occupied, pending))
                self.assertEqual(v.reg(UC_X86_REG_ECX), VV345[game]["manager"][slots])

    def test_reanimate_is_refused_with_no_free_record(self):
        for game, mode, slots in each345(self, ("vv5",)):
            for occupied, refused in ((slots - 1, False), (slots, True)):
                v = Village345(game, mode, slots, occupied, corpses=5)
                where = v.run(0x42341A, {0x4206F0: "slot finder", 0x42341F: "refused"},
                              {UC_X86_REG_EBX: OBJ}, stack=(0xFFFFFFFF,))
                if refused:
                    self.assertEqual(where, "refused")
                    self.assertEqual(v.reg(UC_X86_REG_EAX), 0xFFFFFFFF, "answered as no free spell slot")
                    self.assertEqual(v.reg(UC_X86_REG_ESP), v.esp0 + 4, "its argument popped as 0x4206F0 does")
                else:
                    self.assertEqual(where, "slot finder")
                    self.assertEqual(v.reg(UC_X86_REG_ECX), OBJ)
                    self.assertEqual(v.dword(v.reg(UC_X86_REG_ESP)), 0x42341F)

    def test_the_vial_and_the_crystal_ask_for_records_first(self):
        for game, mode, slots in each345(self, ("vv3",)):
            # the Vial: two copies
            for demand, offered in ((slots - 2, True), (slots - 1, False)):
                v = Village345(game, mode, slots, demand, corpses=4)
                where = v.run(0x4178DA, {}, {UC_X86_REG_EAX: 0x1234, UC_X86_REG_ESI: OBJ},
                              stack=(0xAAAA, SENTINEL))
                self.assertEqual(where, "returned")
                self.assertEqual(v.reg(UC_X86_REG_EAX) & 0xFF, int(offered), demand)
                self.assertEqual(v.dword(OBJ + 4), 0x1234, "the subject is kept as before")
                self.assertEqual(v.reg(UC_X86_REG_ESI), 0xAAAA)
            # the Crystal: one reflection (its own condition is eax < 2)
            for demand, chapter, offered in ((slots - 1, 1, True), (slots, 1, False), (0, 2, False)):
                v = Village345(game, mode, slots, demand, corpses=4)
                where = v.run(0x41580C, {}, {UC_X86_REG_EAX: chapter}, stack=(SENTINEL,))
                self.assertEqual(where, "returned")
                self.assertEqual(v.reg(UC_X86_REG_EAX) & 0xFF, int(offered), (demand, chapter))
            # the Crystal's keep: nothing changes without a record
            for demand, kept in ((slots - 1, True), (slots, False)):
                v = Village345(game, mode, slots, demand, corpses=4)
                v.uc.mem_write(OBJ + 0xC, struct.pack("<I", 0x77))
                where = v.run(0x4191EF, {0x4191F5: "likes change"},
                              {UC_X86_REG_ESI: OBJ, UC_X86_REG_EDI: 0x5151},
                              stack=(0xAAAA, SENTINEL, 0))
                if kept:
                    self.assertEqual(where, "likes change")
                    self.assertEqual((v.dword(v.reg(UC_X86_REG_ESP)), v.dword(v.reg(UC_X86_REG_ESP) + 4)),
                                     (0x2B, 0x5151), "push edi; push 0x2B as the stock code")
                else:
                    self.assertEqual(where, "returned")
                    self.assertEqual(v.dword(OBJ + 0xC), 0, "answered as when the clone fails")
                    self.assertEqual(v.reg(UC_X86_REG_ESP), v.esp0 + 12)

    def test_the_secret_city_s_litter_guards_count_babies_owed(self):
        for game, mode, slots in each345(self, ("vv3",)):
            for guard, kept, refused, need in ((0x47B260, 0x455BC9, 0x455BDD, 3), (0x47B280, 0x455BE7, 0x455BED, 2)):
                # the conceiving mother is in the table, her first baby owed;
                # another mother owes one more
                for others, expect in ((slots - need - 2, "kept"), (slots - need - 1, "refused")):
                    v = Village345(game, mode, slots, others + 1, pending=[(others, 1), (0, 1)])
                    where = v.run(guard, {kept: "kept", refused: "refused"},
                                  {UC_X86_REG_ESI: v.rec(others)})
                    self.assertEqual(where, expect, (hex(guard), others))


if __name__ == "__main__":
    unittest.main()
