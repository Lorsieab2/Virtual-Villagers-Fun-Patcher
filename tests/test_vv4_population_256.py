"""256 Villagers (Experimental), The Tree of Life: the replaced routines, RUN.

Every routine the patch widens is executed here in an emulator, on the stock
executable and on 256 renders, at 0, 1, 149, 150, 151, 255 and 256 villagers:

* the population counter that feeds the cap check, and the male/female tally
  (stock: 25 x 6 unrolled records; now one 256-record loop);
* the three allocators (villager, villager from a template, ghost), which must
  hand out slots 150..255 and refuse at 256;
* the getter, the selection setter, the static constructor and the
  per-record initialiser;
* the save: the payload's stock part is byte-identical to the stock writer's
  for the same village, villagers 150..255 follow it, a 256 save and an old
  150-slot save both load, and a village of exactly 150 no longer overwrites
  the progress block after the stock compact table;
* every other widened routine against stock, with the same villagers in the
  same slots and moved to the top of the 256 table;
* the Villager Details living list, the population cap in every mode, the
  slot-safety rows, and the compositions with every public VV4 patch.

The manager address and slot count come from the executable's own
instructions, so the same code drives the stock and the 256 images.
"""
from __future__ import annotations

import random
import re
import struct
import unittest

from vv4_population_256_harness import (
    ACTIVE,
    COMPACT,
    GHOST,
    HEALTH,
    MODES,
    OWN_INDEX,
    PAYLOAD_256,
    STACK_TOP,
    STOCK_PAYLOAD,
    STRIDE,
    Machine,
    render,
)
import vv_fun_patcher as vfp  # noqa: E402 (the harness puts src on the path)

COUNTS = (0, 1, 149, 150, 151, 255, 256)
SAVE_SLOT = 3
COMPACT_IN_GAME = 0xC868
PROGRESS_BLOCK = 0x160C0          # the 0x4D8BF8 block's size dword, right after the stock table
PROGRESS_SIZE = 0x250


def images():
    """(label, image) for the stock executable and 256 in every mode."""
    yield "stock 150", render("collection_progression", False)
    for mode in MODES:
        yield f"256 {mode}", render(mode, True)


class CountersTests(unittest.TestCase):
    def test_population_and_sex_tally_cover_every_slot(self):
        for label, image in images():
            for n in COUNTS:
                probe = Machine(image)
                if n > probe.slots:
                    continue
                with self.subTest(image=label, villagers=n):
                    m = probe
                    for i in range(n):
                        m.villager(i, sex=i & 1, pregnant=int(i % 7 == 0), babies=2 * int(i % 7 == 0))
                    expected = n + 2 * len([i for i in range(n) if i % 7 == 0])
                    self.assertEqual(m.call(0x467610, ecx=m.manager), expected)
                    out = m.alloc(8)
                    total = m.call(0x467650, [out, out + 4], ecx=m.manager)
                    self.assertEqual((m.u32(out), m.u32(out + 4)), ((n + 1) // 2, n // 2))
                    self.assertEqual(total, n)

    def test_tally_matches_stock_on_every_sex_value(self):
        """Sex 0 and 1 count, any other value does not; health <= 0 never
        counts -- exactly the stock unrolled tests, for records in any slot."""
        stock = Machine(render("collection_progression", False))
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
                total = m.call(0x467650, [out, out + 4], ecx=m.manager)
                males = len([1 for s, h in layout if h > 0 and s == 0])
                females = len([1 for s, h in layout if h > 0 and s == 1])
                self.assertEqual((m.u32(out), m.u32(out + 4), total), (males, females, males + females))
        del stock

    def test_counters_see_only_the_high_slots(self):
        m = Machine(render("collection_progression", True))
        for i in range(150, 256):
            m.villager(i, sex=1)
        self.assertEqual(m.call(0x467610, ecx=m.manager), 106)
        out = m.alloc(8)
        m.call(0x467650, [out, out + 4], ecx=m.manager)
        self.assertEqual((m.u32(out), m.u32(out + 4)), (0, 106))


class AllocatorTests(unittest.TestCase):
    # (allocator, its argument count, the record creator it calls, that
    # creator's stack arguments in bytes)
    ALLOCATORS = ((0x466270, 14, 0x45EF10, 0x38), (0x466310, 1, 0x45D9B0, 4), (0x466370, 7, 0x45EF10, 0x38))

    def _allocate(self, m: Machine, allocator) -> int:
        address, nargs, creator, pop = allocator
        m.created = []
        m.stub(creator, lambda mm: (mm.created.append(mm.reg("ecx")) or 0, pop))
        m.stub(0x45ECB0, lambda mm: (0, 8))              # the ghost's placement
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
                            m.villager(i)
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


class RecordRoutineTests(unittest.TestCase):
    def test_getter(self):
        for label, image in images():
            m = Machine(image)
            for index in (-1, 0, 149, 150, 255, 256, 300):
                with self.subTest(image=label, index=index):
                    got = m.call(0x466040, [index & 0xFFFFFFFF], ecx=m.manager)
                    expected = m.rec(index) if 0 <= index < m.slots else 0
                    self.assertEqual(got, expected)

    def test_selection_setter(self):
        for label, image in images():
            m = Machine(image)
            m.standard_stubs()
            for index in (-1, 0, 149, 150, 255, 256):
                with self.subTest(image=label, index=index):
                    m.put32(m.game + 0x171B0, 0x5A5A)
                    m.call(0x466C90, [index & 0xFFFFFFFF], ecx=m.manager)
                    expected = index & 0xFFFFFFFF if -1 <= index < m.slots else 0x5A5A
                    self.assertEqual(m.u32(m.game + 0x171B0), expected)

    def test_static_constructor_builds_every_record(self):
        for label, image in images():
            m = Machine(image)
            m.call(0x488D70)
            with self.subTest(image=label):
                self.assertEqual(m.u32(m.manager), 0x4AB36C)              # vtable
                # the record constructor points +0x1B88 at the record itself
                built = [m.u32(m.rec(i) + 0x1B88) for i in range(m.slots + 1)]
                self.assertEqual(built[: m.slots], [m.rec(i) for i in range(m.slots)])
                if m.slots == 256:
                    self.assertEqual(built[m.slots], 0)                   # nothing past 256

    def test_initialiser_numbers_every_slot(self):
        for label, image in images():
            m = Machine(image)
            m.standard_stubs()
            m.call(0x465F20, ecx=m.manager)
            with self.subTest(image=label):
                self.assertEqual([m.u32(m.rec(i) + OWN_INDEX) for i in range(m.slots)], list(range(m.slots)))


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
        m.put32(m.game + PROGRESS_BLOCK, PROGRESS_SIZE)   # the size dword the stock loader checks
    for k, i in enumerate(occupied):
        r = m.villager(i, health=40 + k % 50)
        m.put32(r + 0x1B8C, 0x10000 + i)               # saved at compact entry +0x04
        m.put32(r + 0x1E60, 0x20000 + i)               # saved at compact entry +0xEC
    written = {}

    def writer(mm: Machine) -> tuple[int, int]:
        buffer, size, slot = mm.arg(0), mm.arg(1), mm.arg(2)
        written["payload"] = mm.read(buffer, size)
        written["slot"] = slot
        return 1, 12

    m.stub(0x4039B0, writer)
    m.call(0x4660A0, [m.game + COMPACT_IN_GAME], ecx=m.manager)
    # the tail of 0x41F030 from `test esi, esi`: (saved edi, saved esi, return, arg)
    esp = STACK_TOP - 0x20000
    m.write(esp, struct.pack("<IIII", 0, 0, 0x0F000000, SAVE_SLOT))
    m.set_reg("esi", m.game)
    m.set_reg("edi", SAVE_SLOT)
    m.run_until(0x41F12A, 0x0F000000, esp=esp)
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

    m.stub(0x4037E0, reader)
    esp = STACK_TOP - 0x100000
    m.set_reg("ebx", m.game)
    m.set_reg("esi", SAVE_SLOT)
    m.run_until(0x41FBFD, 0x41FC47, esp=esp)          # through the copy into the game state
    m.loaded = m.call(0x466110, [m.game + COMPACT_IN_GAME], ecx=m.manager)
    return m


def _villagers(m: Machine) -> list[tuple[int, int]]:
    return [
        (m.u32(m.rec(i) + 0x1B8C), m.u32(m.rec(i) + 0x1E60))
        for i in range(m.slots)
        if m.u8(m.rec(i) + ACTIVE)
    ]


class SaveTests(unittest.TestCase):
    def test_stock_part_of_the_payload_is_unchanged(self):
        stock = render("collection_progression", False)
        for mode in MODES:
            image = render(mode, True)
            for occupied in ([], [0], list(range(149)), list(range(1, 150))):
                with self.subTest(mode=mode, villagers=len(occupied)):
                    old, _ = _save(stock, occupied)
                    new, _ = _save(image, occupied)
                    self.assertEqual(len(old), 0x18 + STOCK_PAYLOAD)
                    self.assertEqual(len(new), 0x18 + PAYLOAD_256)
                    self.assertEqual(new[0x18 : 0x18 + STOCK_PAYLOAD], old[0x18:])
                    # 149 villagers or fewer: nothing in the extension
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
                        self.assertEqual(struct.unpack_from("<I", entry, 4)[0], 0x10000 + k)
                    else:
                        self.assertEqual(entry, bytes(COMPACT))
                # the stock table is full and its last entry is villager 149
                last = payload[COMPACT_IN_GAME - 8 + 149 * COMPACT :][:COMPACT]
                self.assertEqual(struct.unpack_from("<I", last, 4)[0], 0x10000 + 149)

    def test_round_trip(self):
        for mode in MODES:
            image = render(mode, True)
            for n in COUNTS:
                for layout in ("packed", "scattered"):
                    occupied = list(range(n)) if layout == "packed" else list(range(256 - n, 256))
                    with self.subTest(mode=mode, villagers=n, layout=layout):
                        file, saver = _save(image, occupied)
                        self.assertEqual(saver.u32(saver.game + PROGRESS_BLOCK), PROGRESS_SIZE)
                        self.assertEqual(struct.unpack_from("<I", file, 0x18 + PROGRESS_BLOCK - 8)[0],
                                         PROGRESS_SIZE)
                        loaded = _load(image, file)
                        self.assertEqual(loaded.loaded & 0xFF, 1)
                        # villagers come back renumbered from 0, in slot order
                        self.assertEqual(_villagers(loaded), [(0x10000 + i, 0x20000 + i) for i in occupied])
                        self.assertEqual([loaded.u8(loaded.rec(i) + ACTIVE) for i in range(n)], [1] * n)
                        self.assertEqual(loaded.call(0x467610, ecx=loaded.manager), n)
                        self.assertEqual(loaded.u32(loaded.game + PROGRESS_BLOCK), PROGRESS_SIZE)
                        # saved again, the same file
                        again, _ = _save(image, list(range(n)))
                        if layout == "packed":
                            self.assertEqual(again, file)

    def test_ghosts_and_the_dead_are_not_saved(self):
        image = render("collection_progression", True)
        m_ids = list(range(200))
        file, saver = _save(image, m_ids)
        # same village, with a ghost at 10 and 170 and the dead at 20 and 180
        m = Machine(image)
        m.standard_stubs()
        m.put32(m.game + PROGRESS_BLOCK, PROGRESS_SIZE)
        kept = []
        for i in m_ids:
            r = m.villager(i)
            m.put32(r + 0x1B8C, 0x10000 + i)
            m.put32(r + 0x1E60, 0x20000 + i)
            if i in (10, 170):
                m.put8(r + GHOST, 1)
            elif i in (20, 180):
                m.put8(r + ACTIVE, 0)
            else:
                kept.append(i)
        captured = {}
        m.stub(0x4039B0, lambda mm: (captured.setdefault("p", mm.read(mm.arg(0), mm.arg(1))) and 1, 12))
        m.call(0x4660A0, [m.game + COMPACT_IN_GAME], ecx=m.manager)
        esp = STACK_TOP - 0x20000
        m.write(esp, struct.pack("<IIII", 0, 0, 0x0F000000, SAVE_SLOT))
        m.set_reg("esi", m.game)
        m.set_reg("edi", SAVE_SLOT)
        m.run_until(0x41F12A, 0x0F000000, esp=esp)
        file = b"ldwg" + struct.pack("<IIIII", 0, 0, 0, len(captured["p"]), 0) + captured["p"]
        loaded = _load(image, file)
        self.assertEqual(_villagers(loaded), [(0x10000 + i, 0x20000 + i) for i in kept])
        del saver

    def test_old_150_slot_save_loads_and_upgrades(self):
        stock = render("collection_progression", False)
        for mode in MODES:
            image = render(mode, True)
            for n in (0, 1, 100, 149):
                with self.subTest(mode=mode, villagers=n):
                    old, _ = _save(stock, list(range(n)))
                    loaded = _load(image, old)
                    self.assertEqual(loaded.loaded & 0xFF, 1)
                    self.assertEqual(_villagers(loaded), [(0x10000 + i, 0x20000 + i) for i in range(n)])
                    self.assertEqual(loaded.u32(loaded.game + PROGRESS_BLOCK), PROGRESS_SIZE)
                    # saved again: the 256 format, and it loads back the same
                    again, _ = _save(image, list(range(n)))
                    self.assertEqual(len(again), 0x18 + PAYLOAD_256)
                    self.assertEqual(again[0x18 : 0x18 + STOCK_PAYLOAD], old[0x18:])
                    self.assertEqual(_villagers(_load(image, again)), _villagers(loaded))

    def test_an_old_full_stock_table_stops_at_150(self):
        """A 150-slot save whose stock table is full (no end flag inside it,
        as the fixed 150 build writes 150 villagers) loads exactly 150: the
        empty extension ends the table, the reader never runs past it."""
        stock_file, _ = _save(render("collection_progression", False), list(range(149)))
        payload = bytearray(stock_file[0x18:])
        entry = COMPACT_IN_GAME - 8
        # copy entry 148 into 149 with its own markers: 150 saved villagers
        payload[entry + 149 * COMPACT : entry + 150 * COMPACT] = payload[entry + 148 * COMPACT : entry + 149 * COMPACT]
        struct.pack_into("<I", payload, entry + 149 * COMPACT + 4, 0x10000 + 149)
        struct.pack_into("<I", payload, entry + 149 * COMPACT + 0xEC, 0x20000 + 149)
        file = stock_file[:0x18] + bytes(payload)
        loaded = _load(render("collection_progression", True), file)
        self.assertEqual(_villagers(loaded), [(0x10000 + i, 0x20000 + i) for i in range(150)])
        self.assertEqual(loaded.u8(loaded.rec(150) + ACTIVE), 0)

    def test_a_256_save_is_refused_by_a_stock_build(self):
        file, _ = _save(render("collection_progression", True), list(range(10)))
        m = Machine(render("collection_progression", False))
        m.standard_stubs()
        m.stub(0x4037E0, lambda mm: (int(struct.unpack_from("<I", file, 0x10)[0] == mm.arg(1)), 12))
        m.set_reg("ebx", m.game)
        m.set_reg("esi", SAVE_SLOT)
        m.run_until(0x41FBFD, 0x41FB8F, esp=STACK_TOP - 0x100000)   # the stock load-failed exit

    def test_a_save_of_neither_size_is_refused(self):
        m = Machine(render("collection_progression", True))
        m.standard_stubs()
        m.stub(0x4037E0, lambda mm: (0, 12))
        m.set_reg("ebx", m.game)
        m.set_reg("esi", SAVE_SLOT)
        m.run_until(0x41FBFD, 0x41FB8F, esp=STACK_TOP - 0x100000)

    def test_exactly_150_no_longer_overwrites_the_next_block(self):
        stock = render("collection_progression", False)
        _, saver = _save(stock, list(range(150)))
        # the stock defect this patch does not carry: the end flag lands on
        # the 0x4D8BF8 block's size dword
        self.assertNotEqual(saver.u32(saver.game + PROGRESS_BLOCK), PROGRESS_SIZE)
        _, saver = _save(render("collection_progression", True), list(range(150)))
        self.assertEqual(saver.u32(saver.game + PROGRESS_BLOCK), PROGRESS_SIZE)


FIX = "vv4_fix_vanilla_bugs"
FIX_WRITER, FIX_READER, FIX_CHECK = 0x660F1, 0x6613D, 0x387A0
# Fix Vanilla Bugs' every-default-name rows (the naming routine's roll), which
# the 256 build leaves to the row as it is.
FIX_NAMES = {0x65DB5, 0x65DC1}
BLOCK_CHECK, BLOCK_OBJECT, BLOCK_SIZE_FN = 0x4387A0, 0x4D8BF8, 0x438770


def _render_ids(mode: str, ids: list[str]) -> tuple[bytes, list[dict]]:
    from vv4_population_256_harness import EXE

    build = next(b for b in vfp.load_builds() if b.id == "vv4")
    data, applied = vfp.render_patched_bytes(EXE, build, mode, ids)
    return bytes(data), applied


def _check_block(m: Machine) -> int:
    """The progress block's size check 0x4387A0 on the block the load put
    right after the stock compact table; the size the game computes from its
    sub-objects (0x438770) is the 0x250 it computes in play."""
    m.stub(BLOCK_SIZE_FN, lambda mm: (PROGRESS_SIZE, 0))
    return m.call(BLOCK_CHECK, [m.game + PROGRESS_BLOCK], ecx=BLOCK_OBJECT) & 0xFF


class FixVanillaBugsTests(unittest.TestCase):
    """Fix Vanilla Bugs' exactly-150 rows with 256 Villagers.

    Its save-writer and loader rows fix the very routines 256 Villagers
    replaces (the end flag lives in the 257-entry table), so with 256
    selected they stand aside (`yield_to`) and the 256 rows go onto the stock
    bytes.  Its block-check row stays: it lets a save the unfixed game
    already damaged (150 villagers, the 0x4D8BF8 block's size 0x250 stored
    as 0x200) load with all 150, in the 256 build as in the 150 one."""

    def test_writer_and_reader_rows_yield_the_block_check_stays(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                _, applied = _render_ids(mode, ["vv4_population_256", FIX])
                fix_rows = {int(a["offset"], 0) for a in applied if a.get("owner") == f"feature:{FIX}"}
                self.assertEqual(fix_rows, {FIX_CHECK} | FIX_NAMES)
                _, applied = _render_ids(mode, [FIX])
                fix_rows = {int(a["offset"], 0) for a in applied if a.get("owner") == f"feature:{FIX}"}
                self.assertEqual(fix_rows, {FIX_WRITER, FIX_READER, FIX_CHECK} | FIX_NAMES)

    def test_a_save_the_unfixed_game_damaged_loads_with_all_150(self):
        damaged, saver = _save(render("collection_progression", False), list(range(150)))
        self.assertEqual(saver.u32(saver.game + PROGRESS_BLOCK), 0x200)    # the stock defect
        for mode in MODES:
            image, _ = _render_ids(mode, ["vv4_population_256", FIX])
            with self.subTest(mode=mode):
                loaded = _load(image, damaged)
                self.assertEqual(loaded.loaded & 0xFF, 1)
                self.assertEqual(loaded.u32(loaded.game + PROGRESS_BLOCK), 0x200)
                self.assertEqual(_check_block(loaded), 1)
                self.assertEqual(_villagers(loaded), [(0x10000 + i, 0x20000 + i) for i in range(150)])
                self.assertEqual(loaded.call(0x467610, ecx=loaded.manager), 150)
                again, resaver = _save(image, list(range(150)))
                self.assertEqual(resaver.u32(resaver.game + PROGRESS_BLOCK), PROGRESS_SIZE)
                self.assertEqual(len(again), 0x18 + PAYLOAD_256)
                reloaded = _load(image, again)
                self.assertEqual(_check_block(reloaded), 1)
                self.assertEqual(_villagers(reloaded), _villagers(loaded))
        # without the fix, the 256 build refuses the damaged save like the base game
        alone = _load(render("collection_progression", True), damaged)
        self.assertEqual(_check_block(alone), 0)

    def test_exactly_150_and_256_round_trip_with_the_fix(self):
        for mode in MODES:
            image, _ = _render_ids(mode, ["vv4_population_256", FIX])
            for occupied in (list(range(149)), list(range(150)), list(range(151)), list(range(256))):
                with self.subTest(mode=mode, villagers=len(occupied)):
                    file, saver = _save(image, occupied)
                    self.assertEqual(saver.u32(saver.game + PROGRESS_BLOCK), PROGRESS_SIZE)
                    loaded = _load(image, file)
                    self.assertEqual(_check_block(loaded), 1)
                    self.assertEqual(_villagers(loaded), [(0x10000 + i, 0x20000 + i) for i in occupied])


# ---- every other widened routine, against stock ------------------------
#
# (routine, its arguments, what it returns[, ecx]).  An argument "rec:k" is
# villager k's record, "idx:k" villager k's index, "out" a dword to write to,
# "ax"/"ay" a point inside the last villager.  Returns: "index" (a slot or
# -1), "pointer" (a record address or 0), "value" (compared as is), "bool"
# (AL) or "none" (EAX is left over; only the effects are compared).  ecx is
# the manager unless given ("rec:k" or "obj", a zeroed object).
DIFFERENTIAL = {
    0x466060: ([], "pointer"),
    0x466450: ([], "none"),
    0x4666B0: ([], "none"),
    0x466820: (["ax", "ay"], "index"),
    0x466940: (["ax", "ay", -1, 1], "pointer"),
    0x466941: (["ax", "ay", "idx:2", 0], "pointer"),
    0x466A00: (["ax", "ay", 0], "pointer"),
    0x466AD0: (["rec:2", "ax", "ay"], "pointer"),
    0x466B80: ([], "bool"),
    0x466BF0: ([7], "none"),
    0x466CE0: ([], "index"),
    0x466DA0: (["rec:3"], "index"),
    0x466EB0: (["rec:3"], "index"),
    0x466F40: ([60, 1, 5], "none"),
    0x466FB0: ([], "none"),
    0x466FE0: ([0], "none"),
    0x467040: ([60, 3, 10], "none"),
    0x4670B0: ([60, 5], "none"),
    0x467110: ([60, 1, 2, 3, 4], "none"),
    0x4671A0: ([1, -1, -1, -1, "out"], "none"),
    0x4671A1: ([1, 360, 1000, 1, "out"], "none"),
    0x467290: ([0, 5, -1, -1, -1, "out"], "none"),
    0x467291: ([2, 5, 360, 1000, 1, "out"], "none"),
    0x467380: ([1, 0, -1, -1, -1, 0], "none"),
    0x467381: ([1, 0, 360, 1000, 1, 0], "none"),
    0x4674E0: ([1, 0, 0, 0, -1, -1, -1, 0], "none"),
    0x4674E1: ([1, 0, 0, 0, 360, 1000, 0, 0], "none"),
    0x467490: ([], "none"),
    0x467740: ([], "value"),
    0x467790: ([0], "none"),
    0x467820: ([0x79], "bool"),
    0x467860: ([0x79, 0], "none"),
    0x4678F0: ([1, "out"], "pointer"),
    0x4679B0: ([-1, -1, -1, 1, 1, -1, 0, 0, 0, "out"], "pointer"),
    0x4679B1: ([360, 2000, 1, 0, 0, 2, 0, 0, 0, "out"], "pointer"),
    0x467B00: ([-1, 3, 1, -1, 0, 0], "none"),
    0x467C50: ([1, "out"], "pointer"),
    0x460370: ([300], "pointer", "rec:3"),
}
# Deep routines the widened code hands villagers to (actions, sounds, UI):
# replaced in both runs by a recorder (address -> bytes popped), whose call
# logs -- callee, ECX and two arguments, record addresses taken relative to
# the villager -- must agree.
DEEP = {0x468C60: 0, 0x45DEC0: 8, 0x46A030: 0, 0x46D090: 0, 0x412F90: 8, 0x44B890: 0xC,
        0x45D1F0: 4, 0x44C5A0: 0x10, 0x46AF40: 8, 0x46AF00: 8}
SELECTED = 5                      # the selected villager (GameState+0x171B0)
# 0x466941 is 0x466940 with an excluded index and the living only;
# 0x4679B1 is 0x4679B0 with every filter argument set.
ALIAS = {0x466941: 0x466940, 0x4679B1: 0x4679B0, 0x467381: 0x467380, 0x4674E1: 0x4674E0,
         0x4671A1: 0x4671A0, 0x467291: 0x467290}
REVERSE_SCANS = (0x466820, 0x466A00, 0x466AD0)
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
    struct.pack_into("<I", blob, 0, 0)
    m.put32(r, 2)                              # a candidate for the "+0 == 2" scans
    m.put32(r + 0x1B88, r)                     # the record's self pointer
    m.put8(r + ACTIVE, 1)
    m.put8(r + 0x1CC5, 0)
    m.put8(r + 0x1CC6, 0)
    m.put8(r + GHOST, rnd.choice((0, 0, 0, 0, 1)))
    m.put32(r + HEALTH, rnd.choice((0, 30, 60, 90, 100)))
    m.put32(r + OWN_INDEX, slot)
    m.put32(r + 0x1C94, 300 + rnd.randrange(400))   # position
    m.put32(r + 0x1C98, 300 + rnd.randrange(400))
    m.put32(r + 0x1B8C, rnd.choice((100, 360, 500, 999, 1200)))   # age
    m.put32(r + 0x1B90, rnd.choice((0, 1, 1, 2)))                  # sex
    m.put32(r + 0x1C4C, rnd.choice((0, 0, 1)))                     # pregnant
    m.put8(r + 0x1C48, rnd.choice((0, 0, 1)))
    m.put32(r + 0x1E5C, 0)                     # empty action queue
    for k in range(0x1D14, 0x1D14 + 4 * 0x50, 4):
        m.put32(r + k, 0xFFFFFFFF)


def _differential_run(image: bytes, fn: int, spec, slots, shift: int):
    args, kind = spec[0], spec[1]
    this = spec[2] if len(spec) > 2 else None
    m = Machine(image)
    rolls = random.Random(7)
    m.standard_stubs(lambda n: rolls.randrange(1 << 30))
    m.put32(m.game + 0x171B0, SELECTED + shift)
    m.put32(m.game + 0x17110, 1)              # the day length the ageing tick divides by
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
        if callee == 0x44C5A0 and isinstance(a1, int):
            a1 -= shift                      # the villager's sound takes its index
        mm.log.append((callee, norm(mm.reg("ecx")), a0, a1))
        return 0, pop

    m.log = []
    for callee, pop in DEEP.items():
        m.stub(callee, lambda mm, c=callee, p=pop: record(mm, c, p))
    out = m.alloc(4)
    anchor = {"ax": 0, "ay": 0}
    if slots:
        last = m.rec(slots[-1])
        point = m.alloc(8)
        m.call(0x45ED00, [point], ecx=last)
        anchor = {"ax": m.i32(point) + 1, "ay": m.i32(point + 4) + 1}
        if fn in (0x466820, 0x466940, 0x466941, 0x466A00):
            anchor = {"ax": m.i32(last + 0x1C94) + 1, "ay": m.i32(last + 0x1C98) + 1}
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
    m.effects = (m.log, m.u32(out), m.u32(m.game + 0x171B0) - shift)
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
                m.put8(r + GHOST, 0)
                m.put32(r + HEALTH, 60)
                m.put32(r, 2)
                point = m.alloc(8)
                m.call(0x45ED00, [point], ecx=r)
                if fn == 0x466AD0:
                    args = [0, m.i32(point) + 1, m.i32(point + 4) + 1]
                elif fn == 0x466A00:
                    args = [m.i32(r + 0x1C94) + 1, m.i32(r + 0x1C98) + 1, 0]
                else:
                    args = [m.i32(r + 0x1C94) + 1, m.i32(r + 0x1C98) + 1]
                got = m.call(fn, [v & 0xFFFFFFFF for v in args], ecx=m.manager)
                self.assertIn(got, (255, r))


class PickerStackTests(unittest.TestCase):
    """The ten pickers keep candidate indices in a stack array, now 256
    entries: with every slot a candidate, each roll must be able to pick
    every slot -- including 255 -- and the caller's frame must be intact."""

    def test_every_slot_can_be_picked(self):
        image = render("collection_progression", True)
        for fn, args in ((0x466DA0, ["me"]), (0x466EB0, ["me"]), (0x4678F0, [0x95, "out"]),
                         (0x467C50, [7, "out"]), (0x4679B0, [-1, -1, -1, 1, 1, -1, 0, 0, 0, "out"])):
            for pick in (0, 149, 150, 255):
                with self.subTest(routine=hex(fn), roll=pick):
                    m = Machine(image)
                    m.standard_stubs(lambda n, p=pick: p)
                    me = m.alloc(STRIDE)
                    m.put32(me + HEALTH, 60)
                    m.put32(me + 0x1B8C, 500)            # an adult woman, not pregnant
                    m.put32(me + 0x1B90, 1)
                    for i in range(256):
                        r = m.villager(i, health=60)      # active, living, not a ghost
                        m.put32(r + 0x1B8C, 500)          # adult men, not pregnant
                        m.put8(r + 0x1C48, int(fn == 0x466EB0))   # the flag 0x466EB0 wants set
                        m.put32(r + 0x1CE0, 0x95)         # the job 0x4678F0 asks for
                        m.put32(r + 0x1C54, 7)            # the value 0x467C50 asks for
                        m.put32(r + 0x1C94, 1)            # not where "me" stands
                    out = m.alloc(4)
                    real = [me if a == "me" else out if a == "out" else a & 0xFFFFFFFF for a in args]
                    got = m.call(fn, real, ecx=m.manager)
                    self.assertEqual(m.rng_calls, [256])   # rand(count) over all 256 candidates
                    self.assertTrue(got == pick or got == m.rec(pick), (hex(got), pick))
                    if "out" in args:
                        self.assertEqual(m.u32(out), 256)


class VisitorTests(unittest.TestCase):
    """Loops over every slot that hand each record to another routine: that
    routine sees all the slots, in order."""

    VISITORS = (
        # (loop, the per-record routine (record in ECX), its pops, active-only, living-only)
        (0x466240, 0x45D8A0, 0, False),
        (0x466420, 0x45FAB0, 0, True),
        (0x466D20, 0x465B00, 0, True),
        (0x466D60, 0x45EAE0, 0, True),
    )

    def test_every_slot_is_visited(self):
        for label, image in images():
            for loop, callee, pop, active_only in self.VISITORS:
                with self.subTest(image=label, loop=hex(loop)):
                    m = Machine(image)
                    m.standard_stubs()
                    for i in range(m.slots):
                        m.villager(i)
                    seen = []
                    m.stub(callee, lambda mm: (seen.append(mm.reg("ecx")) or 0, pop))
                    m.call(loop, ecx=m.manager)
                    self.assertEqual(seen, [m.rec(i) for i in range(m.slots)])


def _layout() -> dict:
    feature = next(p for p in vfp.load_fun_patches() if p.id == "vv4_population_256")
    return feature.raw["population_256"]["layout"]


class DetailsScreenTests(unittest.TestCase):
    """The Villager Details screen keeps the living villagers in a list it
    builds (0x448290), sorts (0x448400) and walks with Previous / Next
    (0x4484A0 / 0x448460).  With 151 or more the stock int[150] at 0x4D8E00
    would overwrite its own count at 0x4D9060; the 256 build keeps the list
    in its own 256-entry buffer."""

    def _screen(self, image: bytes, slots: list[int]) -> Machine:
        m = Machine(image)
        m.standard_stubs()
        for k, i in enumerate(slots):
            r = m.villager(i)
            m.put32(r + 0x1B8C, 1000 + 7 * ((k * 37) % len(slots)))   # distinct ages, shuffled
        for va in (0x4D9058, 0x4D905C, 0x4D9064):
            m.put32(va, 0)                    # sort by age, ascending
        m.put32(0x4D9068, 0x5A5A5A5A)          # past the stock list's neighbours
        m.call(0x448290)
        m.call(0x448400)
        return m

    def _list(self, m: Machine) -> list[int]:
        base = int(_layout()["details_list"], 0) if m.slots == 256 else 0x4D8E00
        return [m.u32(base + 4 * k) for k in range(m.u32(0x4D9060))]

    def test_list_holds_every_living_villager_in_order(self):
        for label, image in images():
            for n in COUNTS:
                probe = Machine(image)
                if n > probe.slots:
                    continue
                with self.subTest(image=label, villagers=n):
                    slots = list(range(probe.slots - n, probe.slots))   # the top slots
                    m = self._screen(image, slots)
                    listed = self._list(m)
                    self.assertEqual(sorted(listed), slots)
                    ages = [m.u32(m.rec(i) + 0x1B8C) for i in listed]
                    self.assertEqual(ages, sorted(ages))     # youngest first, as stock sorts
                    self.assertEqual((m.u32(0x4D9058), m.u32(0x4D905C), m.u32(0x4D9068)),
                                     (0, 0, 0x5A5A5A5A))

    def test_same_order_as_stock(self):
        stock = render("collection_progression", False)
        image = render("collection_progression", True)
        for n in (0, 1, 37, 149, 150):
            with self.subTest(villagers=n):
                self.assertEqual(self._list(self._screen(image, list(range(n)))),
                                 self._list(self._screen(stock, list(range(n)))))

    def test_previous_and_next_walk_the_whole_list(self):
        for label, image in images():
            m = self._screen(image, list(range(Machine(image).slots)))
            listed = self._list(m)
            with self.subTest(image=label):
                for start, routine, expected in (
                    (148, 0x448460, 149), (149, 0x448460, 150 % len(listed)),
                    (len(listed) - 1, 0x448460, 0), (0, 0x4484A0, len(listed) - 1),
                    (len(listed) - 1, 0x4484A0, len(listed) - 2),
                ):
                    m.put32(m.game + 0x171B0, listed[start])
                    self.assertEqual(m.call(0x4483B0, [listed[start]]), start)
                    self.assertEqual(m.call(routine, [0, 0]), listed[expected])


class PopulationCapTests(unittest.TestCase):
    """The cap check 0x468350 in every mode, with every number of
    collections and all three huts built."""

    def _cap(self, image: bytes, collections: int) -> int:
        lo, hi = 0, 300
        while lo < hi:                     # the smallest population refused
            n = (lo + hi) // 2
            m = Machine(image)
            for i in range(min(n, m.slots)):
                m.villager(i)
            extra = n - min(n, m.slots)
            if extra:                      # pending babies stand for the rest
                m.put32(m.rec(0) + 0x1C4C, 1)
                m.put32(m.rec(0) + 0x1C50, extra)
            found = {0x46: collections > 0, 0x52: collections > 1, 0x5E: collections > 2, 0x6A: collections > 3}
            m.stub(0x4143F0, lambda mm: (int(found[mm.arg(0)]), 4))
            m.stub(0x438960, lambda mm: (1, 4))
            if m.call(0x468350, ecx=m.manager) & 0xFF:
                lo = n + 1
            else:
                hi = n
        return lo

    def test_caps(self):
        bonus = {0: 0, 1: 5, 2: 10, 3: 15, 4: 25}
        for collections in (0, 1, 2, 3, 4):
            extra = bonus[collections]
            for mode, with_256, expected in (
                ("stock", False, 90 + extra), ("stock", True, 90 + extra),
                ("collection_progression", False, 125 + extra),
                ("collection_progression", True, 231 + extra),
                ("immediate_fixed", False, 150), ("immediate_fixed", True, 256),
            ):
                with self.subTest(mode=mode, with_256=with_256, collections=collections):
                    self.assertEqual(self._cap(render(mode, with_256), collections), expected)


class SlotSafetyTests(unittest.TestCase):
    def test_demand_counter(self):
        """The automatic safety layer's demand counter (0x4890F0) walks the
        relocated table: every occupied record plus the babies a pregnant
        mother still owes a record."""
        for mode in MODES:
            for n in COUNTS:
                with self.subTest(mode=mode, occupied=n):
                    m = Machine(render(mode, True))
                    for i in range(n):
                        m.villager(i, pregnant=int(i == 3), babies=2 if i == 3 else 0)
                    owed = 2 if n > 3 else 0
                    self.assertEqual(m.call(0x4890F0), n + owed)

    def test_guards_compare_against_256(self):
        m = Machine(render("collection_progression", True))
        # The demand already counts the conceiving mother's first baby, so
        # triplets need two more of 256 and twins one more.
        self.assertEqual(m.read(0x489025, 5), bytes.fromhex("3DFE000000"))   # triplets: demand <= 254
        self.assertEqual(m.read(0x489045, 5), bytes.fromhex("3DFF000000"))   # twins: demand <= 255
        self.assertEqual(m.read(0x489065, 5), bytes.fromhex("3D00010000"))   # event newcomer
        self.assertEqual(m.read(0x489085, 5), bytes.fromhex("3D00010000"))   # barrel child

    def test_abandoned_infants_clamp(self):
        """Abandoned Infants asks for min(6, slots left of 256) babies from
        the relocated manager's picker 0x467B00."""
        for n, expected in ((0, 6), (250, 6), (251, 5), (255, 1), (256, None)):
            with self.subTest(occupied=n):
                m = Machine(render("collection_progression", True))
                for i in range(n):
                    m.villager(i)
                asked = []
                m.stub(0x467B00, lambda mm: (asked.append((mm.reg("ecx"), mm.arg(1))) or 0, 0x18))
                m.call(0x4890C0)
                self.assertEqual(asked, [] if expected is None else [(m.manager, expected)])


class OriginsCompanionTests(unittest.TestCase):
    """The Origins companion (the DLL behind the Tech menu) reads the manager
    from 0x488D70 and the slot count from 0x42001C, so its village-wide dry
    runs see every slot of the 256 build: with every villager exactly 18 but
    the one in the top slot, "All Villagers are Exactly 18" has someone to
    change; with that one 18 too, it has no one."""

    DLL = vfp.ROOT / "assets" / "origins" / "VVFP VV4 Origins Icons.dll"

    def _ask(self, mode: str, with_256: bool, odd_one_out: bool) -> str:
        from story_emulator import Process

        proc = Process(render(mode, with_256, True), self.DLL)
        proc.api_handlers["GetForegroundWindow"] = lambda p: (0, 0)
        manager = struct.unpack("<I", proc.read(0x488D71, 4))[0]
        slots = struct.unpack("<I", proc.read(0x42001C, 4))[0]
        self.assertEqual((manager, slots), (0x800000, 256) if with_256 else (0x50E568, 150))
        for i in range(slots):
            r = manager + 0x44 + i * STRIDE
            proc.write(r + ACTIVE, b"\x01")
            proc.put32(r + HEALTH, 50)
            proc.put32(r + 0x1B8C, 500 if odd_one_out and i == slots - 1 else 360)
        proc.export("ConfirmOriginsVillageWide", 8)
        return proc.messages[-1]

    def test_the_top_slot_is_seen(self):
        for mode in MODES:
            for with_256 in (False, True):
                with self.subTest(mode=mode, with_256=with_256):
                    self.assertTrue(self._ask(mode, with_256, True).startswith("Do you want to buy"))
                    self.assertTrue(self._ask(mode, with_256, False).startswith("Everyone is already"))


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


def _leftovers(data: bytes, applied: list[dict]) -> list[str]:
    """Bytes in any other patch's own code that still name the stock table,
    the stock Details list, or a 150-slot bound."""
    found = []
    for item in applied:
        owner = item.get("owner", "")
        offset = int(item["offset"], 0)
        if not item.get("after") or offset < 0x1000 or owner.endswith("_population_256"):
            continue
        blob = data[offset : offset + len(item["after"]) // 2]
        for needle, what in ((struct.pack("<I", 0x50E568), "manager"), (struct.pack("<I", 0x50E5AC), "records"),
                             (struct.pack("<I", 0x4D8E00), "Details list"),
                             (bytes.fromhex("3D96000000"), "cmp eax,150"), (bytes.fromhex("BB96000000"), "mov ebx,150"),
                             (bytes.fromhex("B996000000"), "mov ecx,150"), (bytes.fromhex("0596000000"), "add eax,150")):
            if needle in blob:
                found.append(f"{owner} 0x{offset + blob.index(needle):X} {what}")
    return found


class CompositionTests(unittest.TestCase):
    """256 Villagers with every public VV4 patch: alone with each (and its
    prerequisites), all at once, and all that do not pull in Origins, in
    every mode.  Each renders, and no patch's own code is left naming the
    stock table or a 150-slot bound."""

    def _render(self, mode: str, ids: list[str]) -> tuple[bytes, list[dict]]:
        build = next(b for b in vfp.load_builds() if b.id == "vv4")
        from vv4_population_256_harness import EXE

        data, applied = vfp.render_patched_bytes(EXE, build, mode, ["vv4_population_256", *ids])
        return bytes(data), applied

    def test_every_public_patch(self):
        public = [p.id for p in vfp.load_public_fun_patches()
                  if p.raw.get("game_id") == "vv4" and p.id != "vv4_population_256"]
        origins = {"vv4_enable_origins_exclusive_features"}
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

    def test_round_trip_with_every_public_patch(self):
        for mode in MODES:
            image = render(mode, True, True)
            for n in (149, 150, 256):
                with self.subTest(mode=mode, villagers=n):
                    file, _ = _save(image, list(range(n)))
                    loaded = _load(image, file)
                    self.assertEqual(_villagers(loaded), [(0x10000 + i, 0x20000 + i) for i in range(n)])

    def test_origins_free_slot_walk_reads_the_relocated_table(self):
        """The Origins Tech menu's "no room for the barrel" bit (0x2000000)
        counts free records of the relocated table: set with 254 occupied
        (two free), clear with 253 (three free)."""
        for mode in MODES:
            image = render(mode, True, True)
            m = Machine(image)
            # the walk, found by its shape (mov ecx, first flag; xor esi, esi;
            # mov ebx, records; cmp byte [ecx], 0) whatever its immediates
            walks = [m.start() for m in re.finditer(rb"\xB9.{4}\x31\xF6\xBB.{4}\x80\x39\x00", image, re.S)]
            self.assertEqual(len(walks), 1)
            start = walks[0]
            va = int(vfp._virtual_address_for_offset(image, start), 16)
            every = set(range(256))
            cases = (
                (set(range(253)), False), (set(range(254)), True), (set(), False), (every, True),
                # the only free records are above the stock 150
                (every - {150, 200, 255}, False), (every - {200, 255}, True),
            )
            for occupied, no_room in cases:
                with self.subTest(mode=mode, occupied=len(occupied), free=sorted(every - occupied)[:3]):
                    m = Machine(image)
                    for i in sorted(occupied):
                        m.villager(i)
                    # run the walk: from the composed `mov ecx` to the pops
                    end = image.find(bytes.fromhex("5E5B59"), start)
                    end_va = int(vfp._virtual_address_for_offset(image, end), 16)
                    m.set_reg("edx", 0)
                    m.run_until(va, end_va, esp=STACK_TOP - 0x1000)
                    self.assertEqual(bool(m.reg("edx") & 0x2000000), no_room)

    def test_output_is_named_for_its_own_save_folder(self):
        build = next(b for b in vfp.load_builds() if b.id == "vv4")
        with_256 = [vfp.get_fun_patch("vv4_population_256")]
        self.assertEqual(vfp._output_name(build, "collection_progression", with_256),
                         "Virtual Villagers - The Tree of Life - Modded 256.exe")
        self.assertEqual(vfp._output_name(build, "collection_progression", []),
                         "Virtual Villagers - The Tree of Life - Modded.exe")
        self.assertEqual(vfp.output_folder_for(vfp.ROOT / "x" / "game.exe", build, "stock", with_256,
                                               output_root=vfp.ROOT).name,
                         "Virtual Villagers - The Tree of Life - Modded 256")


if __name__ == "__main__":
    unittest.main()
