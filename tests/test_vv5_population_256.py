"""256 Villagers (Experimental), New Believers: the replaced routines, RUN.

Every routine the patch widens is executed here in an emulator, on the stock
executable and on 256 renders, at 0, 1, 149, 150, 151, 255 and 256 villagers:

* the believer counter that feeds the cap check, and the male/female tally
  (stock: 25 x 6 unrolled records; now one 256-record loop);
* the four allocators (villager, Heathen, child, Reanimate stand-in), which
  must hand out slots 150..255 and refuse at 256;
* the getter, the selection validator, the static constructor, the reset
  and the pending list (its capacity and its per-index mask) on the
  re-laid manager tail;
* the save: the payload's stock part is byte-identical to the stock writer's
  for the same village, villagers 150..255 follow it, a 256 save and an old
  150-slot save both load, and a stock build refuses a 256 save;
* every other widened routine against stock, with the same villagers in the
  same slots and moved to the top of the 256 table;
* the Villager Details believer list, the population cap in every mode, the
  slot-safety rows, and the compositions with every public VV5 patch.

The manager address and slot count come from the executable's own
instructions, so the same code drives the stock and the 256 images.
"""
from __future__ import annotations

import random
import struct
import unittest

from vv5_population_256_harness import (
    ACTIVE,
    BABIES,
    COMPACT,
    EXE,
    HEALTH,
    HEATHEN,
    MODES,
    NURSING,
    OWN_INDEX,
    PAYLOAD_256,
    SEX,
    STACK_TOP,
    STANDIN,
    STOCK_PAYLOAD,
    STRIDE,
    Machine,
    render,
)
import vv_fun_patcher as vfp  # noqa: E402 (the harness puts src on the path)

COUNTS = (0, 1, 149, 150, 151, 255, 256)
SAVE_SLOT = 3
COMPACT_IN_GAME = 0xC90C
SELECTED = 0x17E24                 # GameState: the selected villager's index


def images():
    """(label, image) for the stock executable and 256 in every mode."""
    yield "stock 150", render("collection_progression", False)
    for mode in MODES:
        yield f"256 {mode}", render(mode, True)


def _layout() -> dict:
    feature = next(p for p in vfp.load_fun_patches() if p.id == "vv5_population_256")
    return feature.raw["population_256"]["layout"]


def _tail(m: Machine) -> int:
    """The manager tail (selected index, pending count, list, mask, float)."""
    return m.manager + (int(_layout()["manager_tail"], 0) if m.slots == 256 else 0x1BB220)


def _float(m: Machine) -> int:
    """The tail's float, after the pending mask (0x1BB518 in stock)."""
    return _tail(m) + (0x508 if m.slots == 256 else 0x2F8)


class CountersTests(unittest.TestCase):
    def test_believers_and_sex_tally_cover_every_slot(self):
        for label, image in images():
            for n in COUNTS:
                probe = Machine(image)
                if n > probe.slots:
                    continue
                with self.subTest(image=label, villagers=n):
                    m = probe
                    for i in range(n):
                        m.villager(i, sex=i & 1, heathen=int(i % 10 == 9), standin=int(i % 13 == 12),
                                   nursing=int(i % 7 == 0), babies=2 * int(i % 7 == 0))
                    believers = [i for i in range(n) if i % 10 != 9 and i % 13 != 12]
                    expected = len(believers) + 2 * len([i for i in believers if i % 7 == 0])
                    self.assertEqual(m.call(0x4713F0, ecx=m.manager), expected)
                    out = m.alloc(8)
                    total = m.call(0x4714A0, [out, out + 4], ecx=m.manager)
                    # the tally counts every living record, stand-ins and Heathens too
                    self.assertEqual((m.u32(out), m.u32(out + 4)), ((n + 1) // 2, n // 2))
                    self.assertEqual(total, n)

    def test_tally_matches_stock_on_every_sex_value(self):
        """Sex 0 and 1 count, any other value does not; health <= 0 never
        counts -- exactly the stock unrolled tests, for records in any slot."""
        rnd = random.Random(5)
        layout = [(rnd.choice((-1, 0, 0, 1, 1, 2, 7)), rnd.choice((-5, 0, 1, 40))) for _ in range(150)]
        for image_label, image, shift in (("stock", render("collection_progression", False), 0),
                                          ("256 low", render("collection_progression", True), 0),
                                          ("256 high", render("collection_progression", True), 106)):
            with self.subTest(image=image_label):
                m = Machine(image)
                for k, (sex, health) in enumerate(layout):
                    m.villager(k + shift, sex=sex, health=health)
                out = m.alloc(8)
                m.put32(out, 0xDEAD)
                m.put32(out + 4, 0xBEEF)
                total = m.call(0x4714A0, [out, out + 4], ecx=m.manager)
                males = len([1 for s, h in layout if h > 0 and s == 0])
                females = len([1 for s, h in layout if h > 0 and s == 1])
                self.assertEqual((m.u32(out), m.u32(out + 4), total), (males, females, males + females))

    def test_counters_see_only_the_high_slots(self):
        m = Machine(render("collection_progression", True))
        for i in range(150, 256):
            m.villager(i, sex=1)
        self.assertEqual(m.call(0x4713F0, ecx=m.manager), 106)
        out = m.alloc(8)
        m.call(0x4714A0, [out, out + 4], ecx=m.manager)
        self.assertEqual((m.u32(out), m.u32(out + 4)), (0, 106))


class AllocatorTests(unittest.TestCase):
    # (allocator, its argument count, the record initialiser it calls, that
    # initialiser's stack arguments in bytes)
    ALLOCATORS = (
        (0x46FAD0, 14, 0x4681F0, 0x38),     # a villager
        (0x46FB80, 18, 0x4681F0, 0x38),     # a Heathen
        (0x46FD70, 1, 0x4687F0, 4),         # a child
        (0x46FDE0, 3, 0x4681F0, 0x38),      # a Reanimate stand-in
    )

    def _allocate(self, m: Machine, allocator) -> int:
        address, nargs, creator, pop = allocator
        m.created = []
        m.stub(creator, lambda mm: (mm.created.append(mm.reg("ecx")) or 0, pop))
        # the Heathen's placement and the stand-in's position: not the subject here
        for va, popped in ((0x467F90, 8), (0x466350, 4), (0x4781E0, 0xC), (0x4758B0, 8), (0x466300, 8)):
            m.stub(va, lambda mm, p=popped: (0, p))
        result = m.call(address, [0] * nargs, ecx=m.manager)
        if result != 0xFFFFFFFF:
            self.assertEqual(m.created, [m.rec(result)])
        else:
            self.assertEqual(m.created, [])
        return result

    def test_first_free_slot(self):
        for label, image in images():
            for allocator in self.ALLOCATORS:
                for n in COUNTS:
                    m = Machine(image)
                    if n > m.slots:
                        continue
                    with self.subTest(image=label, allocator=hex(allocator[0]), occupied=n):
                        for i in range(n):
                            m.villager(i, standin=int(i == 5), heathen=int(i == 7), health=0 if i == 9 else 50)
                        expected = n if n < m.slots else 0xFFFFFFFF
                        self.assertEqual(self._allocate(m, allocator), expected)

    def test_last_slot_then_full(self):
        for allocator in self.ALLOCATORS:
            with self.subTest(allocator=hex(allocator[0])):
                m = Machine(render("collection_progression", True))
                for i in range(255):
                    m.villager(i)
                self.assertEqual(self._allocate(m, allocator), 255)
                m.villager(255)
                self.assertEqual(self._allocate(m, allocator), 0xFFFFFFFF)

    def test_a_heathen_lands_in_the_top_slot(self):
        """The Heathen allocator marks the record it hands out as a Heathen
        (0x466880), in slot 255 too."""
        m = Machine(render("collection_progression", True))
        for i in range(255):
            m.villager(i)
        self.assertEqual(self._allocate(m, self.ALLOCATORS[1]), 255)
        self.assertEqual(m.u8(m.rec(255) + HEATHEN), 1)


class RecordRoutineTests(unittest.TestCase):
    def test_getter(self):
        for label, image in images():
            m = Machine(image)
            for index in (-1, 0, 149, 150, 255, 256, 300):
                with self.subTest(image=label, index=index):
                    got = m.call(0x46F950, [index & 0xFFFFFFFF], ecx=m.manager)
                    expected = m.rec(index) if 0 <= index < m.slots else 0
                    self.assertEqual(got, expected)

    def test_selection_validator(self):
        for label, image in images():
            m = Machine(image)
            m.standard_stubs()
            for index in (-1, 0, 149, 150, 255, 256):
                with self.subTest(image=label, index=index):
                    m.put32(m.game + SELECTED, 0x5A5A)
                    m.call(0x4708F0, [index & 0xFFFFFFFF], ecx=m.manager)
                    expected = index & 0xFFFFFFFF if -1 <= index < m.slots else 0x5A5A
                    self.assertEqual(m.u32(m.game + SELECTED), expected)

    def test_manager_selection_lives_in_the_tail(self):
        for label, image in images():
            m = Machine(image)
            with self.subTest(image=label):
                m.call(0x4708D0, [m.slots - 1], ecx=m.manager)
                self.assertEqual(m.u32(_tail(m)), m.slots - 1)
                self.assertEqual(m.call(0x4708E0, ecx=m.manager), m.slots - 1)

    def test_static_constructor_builds_every_record(self):
        for label, image in images():
            m = Machine(image)
            m.call(0x494050)
            with self.subTest(image=label):
                self.assertEqual(m.u32(m.manager), 0x4B8E28)              # vtable
                # the record constructor points +0x1B88 at the record itself
                built = [m.u32(m.rec(i) + 0x1B88) for i in range(m.slots + 1)]
                self.assertEqual(built[: m.slots], [m.rec(i) for i in range(m.slots)])
                self.assertEqual(built[m.slots], 0)                       # nothing past the table

    def test_reset_numbers_every_slot_and_clears_the_tail(self):
        for label, image in images():
            m = Machine(image)
            m.standard_stubs()
            reset = []
            m.stub(0x465100, lambda mm: (reset.append(mm.reg("ecx")) or 0, 0))
            tail = _tail(m)
            m.write(tail, b"\x77" * (8 + 4 * m.slots))
            m.write(tail + 8 + 4 * m.slots, b"\x01" * m.slots)
            m.call(0x46F800, ecx=m.manager)
            with self.subTest(image=label):
                self.assertEqual(reset, [m.rec(i) for i in range(m.slots)])
                self.assertEqual([m.u32(m.rec(i) + OWN_INDEX) for i in range(m.slots)], list(range(m.slots)))
                self.assertEqual(m.read(tail + 8 + 4 * m.slots, m.slots), bytes(m.slots))   # the mask
                self.assertEqual((m.i32(tail), m.u32(tail + 4)), (-1, 0))
                self.assertEqual(m.read(_float(m), 4), struct.pack("<f", 1.0))


class PendingListTests(unittest.TestCase):
    """The pending list (0x471D30 add, 0x471D70 remove) holds up to one entry
    per slot, with a mask by index; both live in the re-laid tail."""

    def test_every_slot_can_be_pending(self):
        for label, image in images():
            m = Machine(image)
            tail = _tail(m)
            with self.subTest(image=label):
                for i in range(m.slots):
                    m.call(0x471D30, [i], ecx=m.manager)
                m.call(0x471D30, [m.slots], ecx=m.manager)            # out of range: refused
                m.call(0x471D30, [5], ecx=m.manager)                  # already pending: refused
                self.assertEqual(m.u32(tail + 4), m.slots)
                self.assertEqual([m.u32(tail + 8 + 4 * k) for k in range(m.slots)], list(range(m.slots)))
                self.assertEqual(m.read(tail + 8 + 4 * m.slots, m.slots), b"\x01" * m.slots)
                # the float after the mask is untouched
                self.assertEqual(m.read(_float(m), 4), bytes(4))
                m.call(0x471D70, [m.slots - 1], ecx=m.manager)
                m.call(0x471D70, [0], ecx=m.manager)
                self.assertEqual(m.u32(tail + 4), m.slots - 2)
                self.assertEqual([m.u32(tail + 8 + 4 * k) for k in range(m.slots - 2)], list(range(1, m.slots - 1)))
                self.assertEqual((m.u8(tail + 8 + 4 * m.slots), m.u8(tail + 8 + 4 * m.slots + m.slots - 1)), (0, 0))

    def test_the_walk_reaches_a_pending_top_slot(self):
        """0x471EB0 walks every record, lists the villagers on job 0x15 and
        counts, per villager INDEX, the spots aimed at them; those nobody aims
        at are acted on.  With 255 villagers listed (the list needs all its
        256 entries) and the one aimed at in slot 201, every count lands in
        the widened, cleared count array and the caller's frame is intact."""
        m = Machine(render("collection_progression", True))
        m.standard_stubs()
        seen = []
        m.stub(0x473440, lambda mm: (seen.append(mm.reg("ecx")) or 0, 0))
        for va, popped in ((0x4671E0, 0), (0x466350, 4), (0x46E2E0, 4), (0x477A80, 8)):
            m.stub(va, lambda mm, p=popped: (0, p))
        # every villager on job 0x15 but 254, on job 0x14 aiming at 201
        for i in range(256):
            m.villager(i)
            m.put32(m.rec(i) + 0x1D10, 0x15)
        m.put32(m.rec(254) + 0x1D10, 0x14)
        m.put32(m.rec(254), 2)
        m.put32(m.rec(254) + 0x14, 201)
        m.call(0x471EB0, ecx=m.manager)
        self.assertEqual(seen, [m.rec(i) for i in range(256) if i not in (201, 254)])


def _save(image: bytes, occupied: list[int], *, canary: bool = True) -> tuple[bytes, Machine]:
    """Run the game's own save code for a village whose occupied slots are
    `occupied`; return the file the stock file writer would have written."""
    m = Machine(image)
    m.standard_stubs()
    # The game state's stock table as a bigger village loaded earlier left it:
    # every entry in use.  The stock writer leaves what lies past its end flag
    # as it was, so only the end flag tells the reader where the village ends.
    m.write(m.game + COMPACT_IN_GAME, bytes([0xA5]) * (150 * COMPACT))
    if m.slots == 256:
        # ...and the 256 build's own compact table, which that load filled
        # from the same file (entry padding the writers never touch included).
        m.write(int(_layout()["compact_table"], 0), bytes([0xA5]) * (256 * COMPACT))
    if canary:
        m.put32(m.game + COMPACT_IN_GAME + 150 * COMPACT, 0x600DF00D)   # the collections block after the table
    for k, i in enumerate(occupied):
        r = m.villager(i, health=40 + k % 50, heathen=int(i % 11 == 3))
        m.put32(r + 0x1B8C, 0x10000 + i)               # saved at compact entry +0x10
        m.put32(r + 0x1F5C, 0x20000 + i)               # saved at compact entry +0xFC
    written = {}

    def writer(mm: Machine) -> tuple[int, int]:
        buffer, size, slot = mm.arg(0), mm.arg(1), mm.arg(2)
        written["payload"] = mm.read(buffer, size)
        written["slot"] = slot
        return 1, 12

    m.stub(0x403940, writer)
    m.call(0x46F9B0, [m.game + COMPACT_IN_GAME], ecx=m.manager)
    # the tail of 0x4244F0 from `test esi, esi`: (saved edi, saved esi, return, arg)
    esp = STACK_TOP - 0x20000
    m.write(esp, struct.pack("<IIII", 0, 0, 0x0F000000, SAVE_SLOT))
    m.set_reg("esi", m.game)
    m.set_reg("edi", SAVE_SLOT)
    m.run_until(0x4245EA, 0x0F000000, esp=esp)
    assert written["slot"] == SAVE_SLOT
    payload = written["payload"]
    header = b"ldwg" + struct.pack("<IIIII", 0x5D1D90F2, 0x5D0E094E, 0, len(payload), 0)
    return header + payload, m


def _load(image: bytes, file: bytes) -> Machine:
    """Run the game's own slot loader from its payload read through the copy
    into the game state, then the compact-table read itself."""
    m = Machine(image)
    m.standard_stubs()

    def reader(mm: Machine) -> tuple[int, int]:
        buffer, size = mm.arg(0), mm.arg(1)
        if file[:4] != b"ldwg" or struct.unpack_from("<I", file, 0x10)[0] != size:
            return 0, 12
        mm.write(buffer, file[0x18 : 0x18 + size])
        return 1, 12

    m.stub(0x403770, reader)
    # the record reset (deep: clocks, singletons): only its active flag matters here
    m.stub(0x465100, lambda mm: (mm.put8(mm.reg("ecx") + ACTIVE, 0) or 0, 0))
    esp = STACK_TOP - 0x100000
    m.set_reg("ebx", m.game)
    m.set_reg("esi", SAVE_SLOT)
    m.run_until(0x4256ED, 0x425737, esp=esp)          # through the copy into the game state
    m.loaded = m.call(0x46FA20, [m.game + COMPACT_IN_GAME], ecx=m.manager)
    return m


def _villagers(m: Machine) -> list[tuple[int, int, int]]:
    return [
        (m.u32(m.rec(i) + 0x1B8C), m.u32(m.rec(i) + 0x1F5C), m.u8(m.rec(i) + HEATHEN))
        for i in range(m.slots)
        if m.u8(m.rec(i) + ACTIVE)
    ]


def _expected(occupied: list[int]) -> list[tuple[int, int, int]]:
    return [(0x10000 + i, 0x20000 + i, int(i % 11 == 3)) for i in occupied]


class SaveTests(unittest.TestCase):
    def test_stock_part_of_the_payload_is_unchanged(self):
        stock = render("collection_progression", False)
        for mode in MODES:
            image = render(mode, True)
            for occupied in ([], [0], list(range(149)), list(range(150)), list(range(1, 150))):
                with self.subTest(mode=mode, villagers=len(occupied)):
                    old, _ = _save(stock, occupied)
                    new, _ = _save(image, occupied)
                    self.assertEqual(len(old), 0x18 + STOCK_PAYLOAD)
                    self.assertEqual(len(new), 0x18 + PAYLOAD_256)
                    self.assertEqual(new[0x18 : 0x18 + STOCK_PAYLOAD], old[0x18:])
                    # 150 villagers or fewer: nothing in the extension
                    self.assertEqual(new[0x18 + STOCK_PAYLOAD :], bytes(PAYLOAD_256 - STOCK_PAYLOAD))

    def test_extension_holds_villagers_150_up_and_zero_after(self):
        image = render("collection_progression", True)
        for n in (150, 151, 200, 255, 256):
            with self.subTest(villagers=n):
                file, _ = _save(image, list(range(n)))
                payload = file[0x18:]
                ext = payload[STOCK_PAYLOAD:]
                for k in range(150, 256):
                    entry = ext[(k - 150) * COMPACT : (k - 149) * COMPACT]
                    if k < n:
                        self.assertEqual(entry[0], 1)
                        self.assertEqual(struct.unpack_from("<I", entry, 0x10)[0], 0x10000 + k)
                        self.assertEqual(entry[1], int(k % 11 == 3))
                    else:
                        self.assertEqual(entry, bytes(COMPACT))
                # the stock table is full and its last entry is villager 149
                last = payload[COMPACT_IN_GAME - 8 + 149 * COMPACT :][:COMPACT]
                self.assertEqual(struct.unpack_from("<I", last, 0x10)[0], 0x10000 + 149)
                # the block after the stock table is the game state's own
                self.assertEqual(struct.unpack_from("<I", payload, COMPACT_IN_GAME - 8 + 150 * COMPACT)[0],
                                 0x600DF00D)

    def test_round_trip(self):
        for mode in MODES:
            image = render(mode, True)
            for n in COUNTS:
                for layout in ("packed", "scattered"):
                    occupied = list(range(n)) if layout == "packed" else list(range(256 - n, 256))
                    with self.subTest(mode=mode, villagers=n, layout=layout):
                        file, _ = _save(image, occupied)
                        loaded = _load(image, file)
                        self.assertEqual(loaded.loaded & 0xFF, 1)
                        # villagers come back renumbered from 0, in slot order
                        self.assertEqual(_villagers(loaded), _expected(occupied))
                        self.assertEqual([loaded.u8(loaded.rec(i) + ACTIVE) for i in range(n)], [1] * n)
                        self.assertEqual(loaded.u32(loaded.game + COMPACT_IN_GAME + 150 * COMPACT), 0x600DF00D)
                        # saved again, the same file
                        again, _ = _save(image, list(range(n)))
                        if layout == "packed":
                            self.assertEqual(again, file)

    def test_stand_ins_and_the_inactive_are_not_saved_as_villagers(self):
        """The writer packs every active record that is not a Reanimate
        stand-in (isActive(0)): Heathens are saved, stand-ins and empty slots
        are not -- in slots above 150 as below."""
        image = render("collection_progression", True)
        m = Machine(image)
        m.standard_stubs()
        kept = []
        for i in range(200):
            r = m.villager(i, heathen=int(i % 11 == 3), standin=int(i in (10, 170)))
            m.put32(r + 0x1B8C, 0x10000 + i)
            m.put32(r + 0x1F5C, 0x20000 + i)
            if i in (20, 180):
                m.put8(r + ACTIVE, 0)
            elif i not in (10, 170):
                kept.append(i)
        captured = {}
        m.stub(0x403940, lambda mm: (captured.setdefault("p", mm.read(mm.arg(0), mm.arg(1))) and 1, 12))
        m.call(0x46F9B0, [m.game + COMPACT_IN_GAME], ecx=m.manager)
        esp = STACK_TOP - 0x20000
        m.write(esp, struct.pack("<IIII", 0, 0, 0x0F000000, SAVE_SLOT))
        m.set_reg("esi", m.game)
        m.set_reg("edi", SAVE_SLOT)
        m.run_until(0x4245EA, 0x0F000000, esp=esp)
        file = b"ldwg" + struct.pack("<IIIII", 0, 0, 0, len(captured["p"]), 0) + captured["p"]
        loaded = _load(image, file)
        self.assertEqual(_villagers(loaded), _expected(kept))

    def test_old_150_slot_save_loads_and_upgrades(self):
        stock = render("collection_progression", False)
        for mode in MODES:
            image = render(mode, True)
            for n in (0, 1, 100, 149, 150):
                with self.subTest(mode=mode, villagers=n):
                    old, _ = _save(stock, list(range(n)))
                    loaded = _load(image, old)
                    self.assertEqual(loaded.loaded & 0xFF, 1)
                    self.assertEqual(_villagers(loaded), _expected(list(range(n))))
                    self.assertEqual(loaded.u8(loaded.rec(n) + ACTIVE) if n < 256 else 0, 0)
                    # saved again: the 256 format, and it loads back the same
                    again, _ = _save(image, list(range(n)))
                    self.assertEqual(len(again), 0x18 + PAYLOAD_256)
                    self.assertEqual(again[0x18 : 0x18 + STOCK_PAYLOAD], old[0x18:])
                    self.assertEqual(_villagers(_load(image, again)), _villagers(loaded))

    def test_a_256_save_is_refused_by_a_stock_build(self):
        file, _ = _save(render("collection_progression", True), list(range(10)))
        m = Machine(render("collection_progression", False))
        m.standard_stubs()
        m.stub(0x403770, lambda mm: (int(struct.unpack_from("<I", file, 0x10)[0] == mm.arg(1)), 12))
        m.set_reg("ebx", m.game)
        m.set_reg("esi", SAVE_SLOT)
        m.run_until(0x4256ED, 0x42567F, esp=STACK_TOP - 0x100000)   # the stock load-failed exit

    def test_a_save_of_neither_size_is_refused(self):
        m = Machine(render("collection_progression", True))
        m.standard_stubs()
        m.stub(0x403770, lambda mm: (0, 12))
        m.set_reg("ebx", m.game)
        m.set_reg("esi", SAVE_SLOT)
        m.run_until(0x4256ED, 0x42567F, esp=STACK_TOP - 0x100000)


# ---- every other widened routine, against stock ------------------------
#
# (routine, its arguments, what it returns[, ecx]).  An argument "rec:k" is
# villager k's record, "idx:k" villager k's index, "out" a dword to write to,
# "ax"/"ay" a point inside the last villager.  Returns: "index" (a slot or
# -1), "pointer" (a record address or 0), "value" (compared as is), "bool"
# (AL) or "none" (EAX is left over; only the effects are compared).
DIFFERENTIAL = {
    0x46F970: ([], "pointer"),
    0x46FE90: ([], "none"),
    0x470100: ([], "none"),
    0x470270: (["ax", "ay"], "index"),
    0x470450: (["ax", "ay", 0, 0], "pointer"),
    0x470451: (["ax", "ay", "rec:2", 1], "pointer"),
    0x4705D0: (["ax", "ay", 0], "pointer"),
    0x470690: ([5], "pointer"),
    0x4706F0: (["rec:3", 400, 0], "pointer"),
    0x4707A0: ([], "bool"),
    0x470810: ([1, 2, 3], "none"),
    0x470940: ([], "index"),
    0x470980: ([1], "none"),
    0x4709D0: ([], "none"),
    0x470A10: (["rec:3"], "index"),
    0x470B40: (["rec:3"], "index"),
    0x470BF0: ([50, 1, 2], "none"),
    0x470C60: ([1, -1, -1, -1, "out", 0], "none"),
    0x470C61: ([1, 360, 1000, 1, "out", 1], "none"),
    0x470D60: ([1, -1, -1, -1, "out", 0], "none"),
    0x470D61: ([2, 100, 2000, 0, "out", 3], "none"),
    0x470E60: ([], "none"),
    0x4710B0: ([1, 50, -1, -1, 0, "out", 0, 1], "none"),
    0x4710B1: ([2, 100, 360, 2000, 1, "out", 2, 0], "none"),
    0x471200: ([1, 2, 30, 30, -1, -1, 0, "out"], "none"),
    0x471201: ([1, 2, 30, 30, 360, 2000, 1, "out"], "none"),
    0x471340: (["rec:3"], "none"),
    0x471450: ([], "value"),
    0x471590: ([], "value"),
    0x4715E0: ([], "none"),
    0x471680: ([5], "bool"),
    0x4716D0: ([5, 1], "none"),
    0x471750: ([], "bool"),
    0x4717A0: ([5, "out"], "pointer"),
    0x471870: ([-1, -1, -1, 0, 0, -1, 0, 0, 0, "out", 0, 0, 0, 0], "pointer"),
    0x471871: ([360, 2000, 1, 1, 0, -1, 0, 0, 1, "out", 1, 0, 1, 0], "pointer"),
    0x471A50: ([0, 1, 0, -1, 0, "out"], "pointer"),
    0x471A51: ([1, 1, 1, 5, 0, "out"], "pointer"),
    0x471BB0: ([5, "out"], "pointer"),
    0x471C50: (["rec:3"], "bool"),
    0x467A40: ([300], "pointer", "rec:3"),
}
ALIAS = {0x470451: 0x470450, 0x470C61: 0x470C60, 0x470D61: 0x470D60, 0x4710B1: 0x4710B0,
         0x471201: 0x471200, 0x471871: 0x471870, 0x471A51: 0x471A50}
# Deep routines the widened code hands villagers to (actions, sounds, UI,
# clocks): replaced in both runs by a recorder (address -> bytes popped),
# whose call logs -- callee, ECX and two arguments, record addresses taken
# relative to the villager -- must agree.
DEEP = {0x473440: 0, 0x465580: 8, 0x473590: 0, 0x4662C0: 4, 0x4662D0: 4, 0x467F90: 8, 0x478730: 0,
        0x464F90: 4, 0x46F3C0: 0, 0x466100: 0, 0x4758F0: 8, 0x430F20: 0xC, 0x477820: 8, 0x44F2E0: 0x10,
        0x413450: 8, 0x465E00: 0x1C, 0x46E2E0: 4, 0x477A80: 8, 0x4671E0: 0, 0x477B90: 0x10, 0x466300: 8,
        0x44E730: 0xC, 0x4036E0: 0, 0x465360: 4, 0x46F7F0: 4}
REVERSE_SCANS = (0x470270, 0x4705D0, 0x4706F0)
SHIFT = 256 - 150


def _fill(m: Machine, slot: int, seed: int) -> None:
    """A villager with every field a small pseudo-random value, so the
    routines' conditions pass for some villagers and fail for others."""
    rnd = random.Random(seed)
    blob = bytearray(STRIDE)
    for k in range(0, STRIDE, 4):
        struct.pack_into("<i", blob, k, rnd.choice((0, 0, 0, 1, 2, 3, 5, 10, 50, 100, 200, 1200, -1)))
    r = m.rec(slot)
    m.write(r, bytes(blob))
    m.put32(r, rnd.choice((2, 3)))             # a candidate for the "+0 == 2" / "+0 == 3" scans
    m.write(r + 0x1CCC, struct.pack("<f", 1.0))   # the drawing scale the hit boxes use
    m.put32(r + 0x1B88, r)                     # the record's self pointer
    m.put8(r + ACTIVE, 1)
    m.put8(r + STANDIN, rnd.choice((0, 0, 0, 0, 1)))
    m.put8(r + HEATHEN, rnd.choice((0, 0, 0, 1)))
    m.put32(r + HEALTH, rnd.choice((0, 30, 60, 90, 100)))
    m.put32(r + OWN_INDEX, slot)
    m.put32(r + 0x1C98, 300 + rnd.randrange(400))   # position
    m.put32(r + 0x1C9C, 300 + rnd.randrange(400))
    m.put32(r + 0x1B8C, rnd.choice((100, 280, 360, 500, 999, 1200)))   # age
    m.put32(r + SEX, rnd.choice((0, 1, 1, 2)))
    m.put32(r + NURSING, rnd.choice((0, 0, 1)))
    m.put32(r + BABIES, rnd.choice((0, 1, 2)))
    m.put8(r + 0x1C48, rnd.choice((0, 0, 1)))
    m.put32(r + 0x1E8C, 0)                     # empty action queue
    m.put32(r + 0x1CFC, rnd.choice((0, 5, 6, 7)))


def _differential_run(image: bytes, fn: int, spec, slots, shift: int):
    args, kind = spec[0], spec[1]
    this = spec[2] if len(spec) > 2 else None
    m = Machine(image)
    rolls = random.Random(7)
    m.standard_stubs(lambda n: rolls.randrange(1 << 30))
    m.put32(m.game + SELECTED, 5 + shift)
    m.put32(m.game + 0x17D7C, 1)              # the day length the per-tick update divides by
    for slot in slots:
        _fill(m, slot, 1000 + slot - shift)
    table_end = m.rec(m.slots)

    def norm(value: int):
        if m.manager <= value < table_end:
            return ("table", value - m.manager - shift * STRIDE)
        if STACK_TOP - 0x200000 <= value < STACK_TOP:
            return "stack"                   # a local: the widened frames move them
        return value

    def record(mm: Machine, callee: int, pop: int):
        a0, a1 = norm(mm.arg(0)), norm(mm.arg(1))
        if callee == 0x44F2E0 and isinstance(a1, int):
            a1 -= shift                      # the draw list takes the villager's index
        mm.log.append((callee, norm(mm.reg("ecx")), a0, a1))
        return 0, pop

    m.log = []
    for callee, pop in DEEP.items():
        m.stub(callee, lambda mm, c=callee, p=pop: record(mm, c, p))
    out = m.alloc(4)
    anchor = {"ax": 0, "ay": 0}
    if slots:
        last = m.rec(slots[-1])
        anchor = {"ax": m.i32(last + 0x1C98) + 1, "ay": m.i32(last + 0x1C9C) + 1}
    real = []
    for a in args:
        if a in ("ax", "ay"):
            real.append(anchor[a])
        elif isinstance(a, str) and a.startswith("rec:"):
            real.append(m.rec(int(a[4:]) + shift))
        elif isinstance(a, str) and a.startswith("idx:"):
            real.append(int(a[4:]) + shift)
        elif a == "out":
            real.append(out)
        else:
            real.append(a)
    ecx = m.manager
    if isinstance(this, str) and this.startswith("rec:"):
        ecx = m.rec(int(this[4:]) + shift)
    eax = m.call(ALIAS.get(fn, fn), [v & 0xFFFFFFFF for v in real], ecx=ecx, limit=50_000_000)
    records = m.read(m.rec(shift), STRIDE * len(slots)) if slots else b""
    m.effects = (m.log, m.u32(out), m.u32(m.game + SELECTED) - shift)
    return m, eax, list(m.rng_calls), records


class DifferentialTests(unittest.TestCase):
    """Each widened routine, run on the stock executable and on 256 with the
    same villagers: in the same slots (0..36 and 0..149), and moved up by 106
    to slots 106..255, the top of the 256 table.  The result, the random rolls
    asked for and every byte of every villager must agree -- the moved run
    maps indices and record addresses by +106."""

    def _check(self, fn: int, stock: bytes, image: bytes, n: int, shift: int) -> int:
        spec = DIFFERENTIAL[fn]
        kind = spec[1]
        ms, es, rs, recs_s = _differential_run(stock, fn, spec, list(range(n)), 0)
        mp, ep, rp, recs_p = _differential_run(image, fn, spec, list(range(shift, shift + n)), shift)
        if kind == "index":
            self.assertEqual(ep, es if es == 0xFFFFFFFF else es + shift)
        elif kind == "pointer":
            if es == 0:
                self.assertEqual(ep, 0)
            else:
                self.assertEqual(ep - mp.manager, es - ms.manager + shift * STRIDE)
        elif kind == "value":
            self.assertEqual(ep, es)
        elif kind == "bool":
            self.assertEqual(ep & 0xFF, es & 0xFF)
        self.assertEqual(rp, rs)
        self.assertEqual(mp.effects, ms.effects)
        for k in range(n):
            a = bytearray(recs_s[k * STRIDE : (k + 1) * STRIDE])
            b = bytearray(recs_p[k * STRIDE : (k + 1) * STRIDE])
            ra, rb = ms.rec(k), mp.rec(k + shift)
            # fields holding the record's own slot or address move with it
            for field, va, vb in ((OWN_INDEX, k, k + shift), (0x1B88, ra, rb)):
                if struct.unpack_from("<I", a, field)[0] == va and struct.unpack_from("<I", b, field)[0] == vb:
                    b[field : field + 4] = a[field : field + 4]
            self.assertEqual(bytes(b), bytes(a), f"villager {k} differs")
        return es

    def test_same_slots_and_top_slots(self):
        stock = render("collection_progression", False)
        image = render("collection_progression", True)
        for fn in DIFFERENTIAL:
            for n, shift in ((37, 0), (150, 0), (150, SHIFT)):
                with self.subTest(routine=hex(fn), villagers=n, first_slot=shift):
                    self._check(fn, stock, image, n, shift)

    def test_reverse_scans_reach_the_top_slot(self):
        """Only villager 255 is a candidate: every reverse scan must find it
        (a scan that still started at record 149 would not)."""
        image = render("collection_progression", True)
        for fn in REVERSE_SCANS:
            with self.subTest(routine=hex(fn)):
                m = Machine(image)
                m.standard_stubs()
                _fill(m, 255, 99)
                r = m.rec(255)
                m.put8(r + STANDIN, 0)
                m.put8(r + HEATHEN, 0)
                m.put32(r + HEALTH, 60)
                m.put32(r, 3)
                x, y = m.i32(r + 0x1C98) + 1, m.i32(r + 0x1C9C) + 1
                point = m.alloc(8)
                m.call(0x466350, [point], ecx=r)          # where the villager is drawn
                args = {0x470270: [x, y], 0x4705D0: [x, y, 0],
                        0x4706F0: [0, m.i32(point), m.i32(point + 4)]}[fn]
                got = m.call(fn, [v & 0xFFFFFFFF for v in args], ecx=m.manager)
                self.assertIn(got, (255, r))


class PickerStackTests(unittest.TestCase):
    """The pickers keep candidate indices in stack arrays, now 256 entries:
    with every slot a candidate, each roll must be able to pick every slot --
    including 255 -- and the caller's frame must be intact."""

    def test_every_slot_can_be_picked(self):
        image = render("collection_progression", True)
        for fn, args in ((0x470B40, ["me"]), (0x4717A0, [0x95, "out"]), (0x471BB0, [7, "out"]),
                         (0x471870, [-1, -1, -1, 0, 1, -1, 0, 0, 0, "out", 0, 1, 0, 0])):
            for pick in (0, 149, 150, 255):
                with self.subTest(routine=hex(fn), roll=pick):
                    m = Machine(image)
                    m.standard_stubs(lambda n, p=pick: p)
                    me = m.alloc(STRIDE)
                    m.put32(me + HEALTH, 60)
                    m.put32(me + 0x1C98, 5000)
                    for i in range(256):
                        r = m.villager(i, health=60)      # active, living believers
                        m.put32(r + 0x1B8C, 500)          # adults
                        m.put8(r + 0x1C48, 1)             # the flag 0x470B40 wants set
                        m.put32(r + 0x1D10, 0x95)         # the job 0x4717A0 asks for
                        m.put32(r + 0x1C54, 7)            # the value 0x471BB0 asks for
                        m.put32(r + 0x1C98, 1)            # not where "me" stands
                    out = m.alloc(4)
                    real = [me if a == "me" else out if a == "out" else a & 0xFFFFFFFF for a in args]
                    got = m.call(fn, real, ecx=m.manager)
                    self.assertEqual(m.rng_calls, [256])   # rand(count) over all 256 candidates
                    self.assertTrue(got == pick or got == m.rec(pick), (hex(got), pick))

    def test_group_pickers_act_on_every_slot(self):
        """The Island Event group pickers hand every matching villager -- all
        256 -- to the action, reading their arguments from above the widened
        arrays: 0x470C60 the believers, 0x470D60 the Heathens, 0x4710B0 a
        random share (every one when the roll always passes) through its
        second list."""
        image = render("collection_progression", True)
        for fn, args, heathens in ((0x470C60, [7, -1, -1, -1, "out", 0], 0),
                                   (0x470D60, [7, -1, -1, -1, "out", 0], 1),
                                   (0x4710B0, [7, 101, -1, -1, -1, "out", 0, 256], 0)):
            with self.subTest(routine=hex(fn)):
                m = Machine(image)
                m.standard_stubs(lambda n: 0)
                acted = []
                m.stub(0x473440, lambda mm: (acted.append(mm.reg("ecx")) or 0, 0))
                m.stub(0x465580, lambda mm: (0, 8))
                m.stub(0x473590, lambda mm: (0, 0))
                for i in range(256):
                    r = m.villager(i, health=60, heathen=heathens)
                    m.put32(r + 0x1B8C, 500)
                out = m.alloc(4)
                real = [out if a == "out" else a & 0xFFFFFFFF for a in args]
                m.call(fn, real, ecx=m.manager)
                self.assertEqual(m.u32(out), 256)
                self.assertEqual(sorted(acted), [m.rec(i) for i in range(256)])


class VisitorTests(unittest.TestCase):
    """Loops over every slot that hand each record to another routine: that
    routine sees all the slots, in order."""

    VISITORS = (
        # (loop, its arguments, the per-record routine (record in ECX), its pops)
        (0x46FAA0, [], 0x465100, 0),
        (0x4709D0, [], 0x466100, 0),
        (0x470980, [0], 0x46F3C0, 0),
    )

    def test_every_slot_is_visited(self):
        for label, image in images():
            for loop, args, callee, pop in self.VISITORS:
                with self.subTest(image=label, loop=hex(loop)):
                    m = Machine(image)
                    m.standard_stubs()
                    for i in range(m.slots):
                        m.villager(i)
                    seen = []
                    m.stub(callee, lambda mm: (seen.append(mm.reg("ecx")) or 0, pop))
                    m.call(loop, args, ecx=m.manager)
                    self.assertEqual(seen, [m.rec(i) for i in range(m.slots)])

    def test_getter_loops_outside_the_manager_reach_every_index(self):
        """Code outside the manager that walks the villagers by index through
        the getter (0x41F170: the per-villager update the companions' slot
        count is read from) asks for every index of the table."""
        for label, image in images():
            with self.subTest(image=label):
                m = Machine(image)
                m.standard_stubs()
                asked = []
                m.stub(0x46F950, lambda mm: (asked.append(mm.arg(0)) or mm.rec(mm.arg(0)), 4))
                m.call(0x41F170, ecx=m.manager)
                self.assertEqual(asked, list(range(m.slots)))


class DetailsScreenTests(unittest.TestCase):
    """The Villager Details screen keeps the living believers in a list it
    builds (0x44B890), sorts (0x44BA10) and walks with Next / Previous
    (0x44BA70 / 0x44BAB0).  With 151 or more the stock int[150] at 0x51E220
    would overwrite the Details state after it (0x51E478, 0x51E47C), its own
    count (0x51E480) and the panel pointer (0x51E484); the 256 build keeps
    the list in its own 256-entry buffer."""

    def _screen(self, image: bytes, slots: list[int]) -> Machine:
        m = Machine(image)
        m.standard_stubs()
        for k, i in enumerate(slots):
            r = m.villager(i)
            m.put32(r + 0x1B8C, 1000 + 7 * ((k * 37) % len(slots)))   # distinct ages, shuffled
        # a Heathen, a stand-in and the dead are never listed
        if m.slots == 256 and slots and slots[0] > 3:
            m.villager(0, heathen=1)
            m.villager(1, standin=1)
            m.villager(2, health=0)
        for va in (0x51E478, 0x51E47C):
            m.put32(va, 0)                    # sort by age, ascending
        m.put32(0x51E484, 0x5A5A5A5A)          # the panel pointer after the count
        m.call(0x44B890)
        m.call(0x44BA10)
        return m

    def _list(self, m: Machine) -> list[int]:
        base = int(_layout()["details_list"], 0) if m.slots == 256 else 0x51E220
        return [m.u32(base + 4 * k) for k in range(m.u32(0x51E480))]

    def test_list_holds_every_living_believer_in_order(self):
        for label, image in images():
            for n in COUNTS:
                probe = Machine(image)
                if n > probe.slots or (n > probe.slots - 3 and probe.slots == 256 and n != 256):
                    continue
                with self.subTest(image=label, villagers=n):
                    slots = list(range(probe.slots - n, probe.slots))   # the top slots
                    m = self._screen(image, slots)
                    listed = self._list(m)
                    self.assertEqual(sorted(listed), slots)
                    ages = [m.u32(m.rec(i) + 0x1B8C) for i in listed]
                    self.assertEqual(ages, sorted(ages))     # youngest first, as stock sorts
                    self.assertEqual((m.u32(0x51E478), m.u32(0x51E47C), m.u32(0x51E484)),
                                     (0, 0, 0x5A5A5A5A))

    def test_same_order_as_stock(self):
        stock = render("collection_progression", False)
        image = render("collection_progression", True)
        for n in (0, 1, 37, 149, 150):
            with self.subTest(villagers=n):
                self.assertEqual(self._list(self._screen(image, list(range(n)))),
                                 self._list(self._screen(stock, list(range(n)))))

    def test_next_and_previous_walk_the_whole_list(self):
        for label, image in images():
            m = self._screen(image, list(range(Machine(image).slots)))
            listed = self._list(m)
            with self.subTest(image=label):
                self.assertEqual(len(listed), m.slots)
                for start, routine, expected in (
                    (148, 0x44BA70, 149), (149, 0x44BA70, 150 % len(listed)),
                    (len(listed) - 1, 0x44BA70, 0), (0, 0x44BAB0, len(listed) - 1),
                    (len(listed) - 1, 0x44BAB0, len(listed) - 2),
                ):
                    m.put32(m.game + SELECTED, listed[start])
                    self.assertEqual(m.call(0x44B9C0, [listed[start]]), start)
                    self.assertEqual(m.call(routine, [0, 0]), listed[expected])


class PopulationCapTests(unittest.TestCase):
    """The cap check 0x472BD0 in every mode, with every number of
    collections and all three huts built."""

    def _cap(self, image: bytes, collections: int) -> int:
        lo, hi = 0, 300
        while lo < hi:                     # the smallest population refused
            n = (lo + hi) // 2
            m = Machine(image)
            for i in range(min(n, m.slots)):
                m.villager(i)
            extra = n - min(n, m.slots)
            if extra:                      # nursing babies stand for the rest
                m.put32(m.rec(0) + NURSING, 1)
                m.put32(m.rec(0) + BABIES, extra)
            found = {0x68: collections > 0, 0x50: collections > 1}
            m.stub(0x414690, lambda mm: (int(found[mm.arg(0)]), 4))
            m.stub(0x43AE80, lambda mm: (1, 4))
            if m.call(0x472BD0, ecx=m.manager) & 0xFF:
                lo = n + 1
            else:
                hi = n
        return lo

    def test_caps(self):
        bonus = {0: 0, 1: 5, 2: 15}
        for collections in (0, 1, 2):
            extra = bonus[collections]
            for mode, with_256, expected in (
                ("stock", False, 90 + extra), ("stock", True, 90 + extra),
                ("collection_progression", False, 135 + extra),
                ("collection_progression", True, 241 + extra),
                ("immediate_fixed", False, 150), ("immediate_fixed", True, 256),
            ):
                with self.subTest(mode=mode, with_256=with_256, collections=collections):
                    self.assertEqual(self._cap(render(mode, with_256), collections), expected)


class SlotSafetyTests(unittest.TestCase):
    def test_demand_counter(self):
        """The automatic safety layer's demand counter (0x4944C0) walks the
        relocated table: every active record (Heathens and stand-ins too)
        plus the babies a nursing mother still owes a record."""
        for mode in MODES:
            for n in COUNTS:
                with self.subTest(mode=mode, occupied=n):
                    m = Machine(render(mode, True))
                    for i in range(n):
                        m.villager(i, heathen=int(i == 4), standin=int(i == 6),
                                   nursing=int(i == 3), babies=2 if i == 3 else 0)
                    owed = 2 if n > 3 else 0
                    self.assertEqual(m.call(0x4944C0), n + owed)

    def test_guards_compare_against_256(self):
        m = Machine(render("collection_progression", True))
        # The demand already counts the conceiving mother's first baby.
        self.assertEqual(m.read(0x494345, 5), bytes.fromhex("3DFE000000"))   # triplets: demand <= 254
        self.assertEqual(m.read(0x494365, 5), bytes.fromhex("3DFF000000"))   # twins: demand <= 255
        for va in (0x494565, 0x494585, 0x4945A5):                           # the barrels and the chute
            self.assertEqual(m.read(va, 5), bytes.fromhex("3D00010000"))

    def test_twins_and_triplets_need_free_slots_of_256(self):
        """The birth guards keep triplets only with three of 256 slots free
        and twins with two, else fall through to fewer.  The mother is in the
        table, pregnant with her first baby (the conception writes it before
        the guard), so `others` villagers plus her record and her baby are
        the demand."""
        image = render("collection_progression", True)
        for others, triplets, twins in ((0, True, True), (252, True, True), (253, False, True), (254, False, False)):
            with self.subTest(others=others):
                m = Machine(image)
                for i in range(others):
                    m.villager(i)
                mother = m.villager(others, nursing=300)
                for guard, kept, litter, resume_kept, resume_refused in (
                    (0x494340, triplets, 3, 0x465F1A, 0x465F23),
                    (0x494360, twins, 2, 0x465F2D, 0x465F34),
                ):
                    m.put32(mother + BABIES, 1)
                    m.set_reg("esi", mother)
                    until = resume_kept if kept else resume_refused
                    m.run_until(guard, until, esp=STACK_TOP - 0x1000)
                    self.assertEqual(m.u32(mother + BABIES), litter if kept else 1)

    def test_abandoned_infants_clamp(self):
        """Abandoned Infants asks for min(6, slots left of 256) babies from
        the relocated manager's picker 0x471A50 (its second argument)."""
        image = render("collection_progression", True)
        for n, expected in ((0, 6), (250, 6), (251, 5), (255, 1), (256, None)):
            with self.subTest(occupied=n):
                m = Machine(image)
                for i in range(n):
                    m.villager(i)
                asked = []
                m.stub(0x471A50, lambda mm: (asked.append((mm.reg("ecx"), mm.arg(1))) or 0, 0x18))
                m.call(0x4945E0)
                self.assertEqual(asked, [] if expected is None else [(m.manager, expected)])


class OriginsPageMaskTests(unittest.TestCase):
    """The Origins page's mask helpers (a nibble per villager, keyed by the
    record's index) are composed to the relocated table and to the 256 build's
    own 128-byte mask table: villager 255's nibble lands in its last byte, and
    the stock table's neighbours (0x7B1D6C, the companion's cached export)
    are never touched."""

    def _helpers(self, image: bytes) -> tuple[int, int]:
        m = Machine(image)
        records = struct.pack("<I", m.manager + 0x48)
        at = image.find(b"\x89\xF0\x2D" + records + b"\x72")
        second = image.find(b"\x89\xF0\x2D" + records + b"\x72", at + 1)
        self.assertGreater(at, 0)
        self.assertGreater(second, at)
        return (int(vfp._virtual_address_for_offset(image, at), 16),
                int(vfp._virtual_address_for_offset(image, second), 16))

    def test_every_slot_has_its_own_nibble(self):
        for mode in MODES:
            for with_256 in (False, True):
                image = render(mode, with_256, True)
                get, put = self._helpers(image)
                m = Machine(image)
                table = int(_layout()["mask_table"], 0) if with_256 else 0x7B1D20
                with self.subTest(mode=mode, with_256=with_256):
                    m.put32(0x7B1D6C, 0x5A5A5A5A)
                    for i in range(m.slots):
                        m.set_reg("esi", m.rec(i))
                        m.set_reg("ebx", 1 + i % 5)
                        m.call(put)
                    m.set_reg("esi", m.rec(m.slots))              # past the table: no-op
                    m.set_reg("ebx", 5)
                    m.call(put)
                    expected = bytes((1 + (2 * k) % 5) | ((1 + (2 * k + 1) % 5) << 4) for k in range(m.slots // 2))
                    self.assertEqual(m.read(table, m.slots // 2), expected)
                    self.assertEqual(m.u32(0x7B1D6C), 0x5A5A5A5A)
                    for i in (0, 149, m.slots - 1):
                        m.set_reg("esi", m.rec(i))
                        self.assertEqual(m.call(get), 1 + i % 5)


class OriginsCompanionTests(unittest.TestCase):
    """The Origins companion (the DLL behind the Tech and Villager menus)
    reads the record base and slot count from the executable, so Equal
    Division -- handed the first record by the page -- divides every believer
    of the 256 build: with all 256 slots living believers it sets 256 job
    preferences, and 150 in a 150-slot build."""

    DLL = vfp.ROOT / "data" / "candidates" / "VVFP VV5 Task9 Origins Icons.dll"

    def _divide(self, mode: str, with_256: bool) -> str:
        from story_emulator import Process

        proc = Process(render(mode, with_256, True), self.DLL)
        manager = struct.unpack("<I", proc.read(0x494051, 4))[0]
        slots = struct.unpack("<I", proc.read(0x41F1E6, 4))[0]
        self.assertEqual((manager, slots), (0x800000, 256) if with_256 else (0x554148, 150))
        for i in range(slots):
            r = manager + 0x48 + i * STRIDE
            proc.write(r + ACTIVE, b"\x01")
            proc.put32(r + HEALTH, 50)
            proc.put32(r + SEX, i & 1)
            proc.put32(r + 0x1C74, 9)                 # no profession yet
        proc.export("ApplyVV5EqualDivision", manager + 0x48, 0)
        return proc.messages[-1]

    def test_every_slot_is_divided(self):
        for mode in MODES:
            for with_256 in (False, True):
                with self.subTest(mode=mode, with_256=with_256):
                    message = self._divide(mode, with_256)
                    self.assertTrue(message.startswith(f"Set {256 if with_256 else 150} Villagers' Job Preferences."), message)


def _with_prerequisites(ids: list[str]) -> list[str]:
    catalog = {p.id: p for p in vfp.load_fun_patches()}
    out: list[str] = []

    def add(feature_id: str) -> None:
        if feature_id in out:
            return
        for dependency in vfp._dependency_ids(catalog[feature_id]):
            add(dependency)
        out.append(feature_id)

    for feature_id in ids:
        add(feature_id)
    return out


STOCK_TABLE_NEEDLES = (
    (struct.pack("<I", 0x554148), "manager"), (struct.pack("<I", 0x554190), "records"),
    (struct.pack("<I", 0x51E220), "Details list"), (struct.pack("<I", 0x7B1D20), "mask table"),
    (bytes.fromhex("3D96000000"), "cmp eax,150"), (bytes.fromhex("BB96000000"), "mov ebx,150"),
    (bytes.fromhex("81FB96000000"), "cmp ebx,150"), (bytes.fromhex("BA96000000"), "mov edx,150"),
    (bytes.fromhex("0596000000"), "add eax,150"), (bytes.fromhex("813DE6F1410096000000"), "slot gate 150"),
)


def _leftovers(data: bytes, applied: list[dict]) -> list[str]:
    """Bytes in any other patch's own code that still name the stock table,
    its record 0, the stock Details list or mask table, or a 150-slot bound."""
    found = []
    for item in applied:
        owner = item.get("owner", "")
        offset = int(item["offset"], 0)
        if not item.get("after") or offset < 0x1000 or owner.endswith("_population_256"):
            continue
        blob = data[offset : offset + len(item["after"]) // 2]
        for needle, what in STOCK_TABLE_NEEDLES:
            at = blob.find(needle)
            while at >= 0:
                found.append(f"{owner} 0x{offset + at:X} {what}")
                at = blob.find(needle, at + 1)
        # an absolute operand into a stock record (the Cure All counter)
        for at in range(0, len(blob) - 3):
            value = struct.unpack_from("<I", blob, at)[0]
            if 0x554190 <= value < 0x554190 + 150 * STRIDE and blob[at - 2 : at] == b"\xFF\x05":
                found.append(f"{owner} 0x{offset + at:X} stock record field")
    return found


class CompositionTests(unittest.TestCase):
    """256 Villagers with every public VV5 patch: alone with each (and its
    prerequisites), all at once, and all that do not pull in Origins, in
    every mode.  Each renders, and no patch's own code is left naming the
    stock table or a 150-slot bound."""

    def _render(self, mode: str, ids: list[str]) -> tuple[bytes, list[dict]]:
        build = next(b for b in vfp.load_builds() if b.id == "vv5")
        data, applied = vfp.render_patched_bytes(EXE, build, mode, ["vv5_population_256", *ids])
        return bytes(data), applied

    def test_every_public_patch(self):
        public = [p.id for p in vfp.load_public_fun_patches()
                  if p.raw.get("game_id") == "vv5" and p.id != "vv5_population_256"]
        origins = {"vv5_enable_origins_exclusive_features"}
        no_origins = [i for i in public if not origins & set(_with_prerequisites([i]))]
        selections = [("all", public), ("all without Origins", no_origins)]
        selections += [(i, _with_prerequisites([i])) for i in public]
        for mode in MODES:
            for label, ids in selections:
                with self.subTest(mode=mode, selection=label):
                    data, applied = self._render(mode, ids)
                    self.assertEqual(_leftovers(data, applied), [])
                    m = Machine(data)
                    self.assertEqual((m.manager, m.slots), (0x800000, 256))

    def test_the_stock_build_names_what_the_composition_rewrites(self):
        """The leftovers check is not vacuous: the same selections without
        256 Villagers do name the stock table."""
        build = next(b for b in vfp.load_builds() if b.id == "vv5")
        public = [p.id for p in vfp.load_public_fun_patches()
                  if p.raw.get("game_id") == "vv5" and p.id != "vv5_population_256"]
        data, applied = vfp.render_patched_bytes(EXE, build, "collection_progression", public)
        found = _leftovers(bytes(data), applied)
        for what in ("manager", "records", "mask table", "slot gate 150"):
            self.assertTrue(any(f.endswith(what) for f in found), what)
        # No public patch writes into a stock record any more (the Origins
        # Cure All loop that did was unreachable and is removed since
        # v1.35.52), so the record-field scan is shown to fire on its own.
        blob = bytes.fromhex("90FF05" + struct.pack("<I", 0x554190 + 0x77C).hex() + "90")
        planted = [{"offset": "0x2000", "after": blob.hex(), "owner": "feature:planted"}]
        image = bytearray(0x3000)
        image[0x2000 : 0x2000 + len(blob)] = blob
        self.assertEqual(_leftovers(bytes(image), planted), ["feature:planted 0x2003 stock record field"])

    def test_round_trip_with_every_public_patch(self):
        for mode in MODES:
            image = render(mode, True, True)
            for n in (149, 150, 256):
                with self.subTest(mode=mode, villagers=n):
                    file, _ = _save(image, list(range(n)))
                    loaded = _load(image, file)
                    self.assertEqual(_villagers(loaded), _expected(list(range(n))))

    def test_heathen_mommy_moves_with_the_table(self):
        """Heathen Mommy Puzzle Restoration replaces one stock `mov ecx,
        manager` with a jump to its own sequence; that row stands aside and
        the sequence names the relocated manager."""
        for mode in MODES:
            with self.subTest(mode=mode):
                data, applied = self._render(mode, ["vv5_heathen_mommy_puzzle"])
                self.assertEqual(data[0x24F69:0x24F6E], bytes.fromhex("E9B2F60600"))
                self.assertEqual(data[0x94620:0x9466C].count(bytes.fromhex("B900008000")), 3)

    def test_output_is_named_for_its_own_save_folder(self):
        build = next(b for b in vfp.load_builds() if b.id == "vv5")
        with_256 = [vfp.get_fun_patch("vv5_population_256")]
        self.assertEqual(vfp._output_name(build, "collection_progression", with_256),
                         "Virtual Villagers - New Believers - Modded 256.exe")
        self.assertEqual(vfp._output_name(build, "collection_progression", []),
                         "Virtual Villagers - New Believers - Modded.exe")
        self.assertEqual(vfp.output_folder_for(vfp.ROOT / "x" / "game.exe", build, "stock", with_256,
                                               output_root=vfp.ROOT).name,
                         "Virtual Villagers - New Believers - Modded 256")


if __name__ == "__main__":
    unittest.main()
