"""256 Villagers (Experimental), The Secret City: the replaced routines, RUN.

Every routine the patch widens is executed here in an emulator, on the stock
executable and on 256 renders, at 0, 1, 149, 150, 151, 255 and 256 villagers:

* the population counter that feeds the cap check and the male/female counter
  (the two 15 x 10 unrolled loops, now 26 x 10);
* the three allocators, which must hand out slots 150..255 and never one of the
  four zero padding records;
* the index validator, the cure-all outcome, the static constructor and the
  per-record initialiser;
* the save: the payload's stock part is byte-identical to the stock writer's
  for the same village, villagers 150..255 follow it, a 256 save and an old
  150-slot save both load, and a village of exactly 150 no longer overwrites
  the block after the stock compact table.

The manager address and slot count come from the executable's own
instructions, so the same code drives the stock and the 256 images.
"""
from __future__ import annotations

import random
import struct
import unittest

from vv3_population_256_harness import (
    COMPACT,
    MODES,
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
COMPACT_IN_GAME = 0x786C
STOCK_TAIL_BLOCK = 0x11ED4          # first dword after the stock compact table


def images():
    """(label, image) for the stock executable and 256 in every mode."""
    yield "stock 150", render("collection_progression", False)
    for mode in MODES:
        yield f"256 {mode}", render(mode, True)


class CountersTests(unittest.TestCase):
    def test_population_and_sex_counters_cover_every_slot(self):
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
                    self.assertEqual(m.call(0x45E8F0, ecx=m.manager), expected)
                    out = m.alloc(8)
                    m.call(0x45EA80, [out, out + 4], ecx=m.manager)
                    self.assertEqual((m.u32(out), m.u32(out + 4)), ((n + 1) // 2, n // 2))

    def test_counters_see_only_the_high_slots(self):
        m = Machine(render("collection_progression", True))
        for i in range(150, 256):
            m.villager(i)
        self.assertEqual(m.call(0x45E8F0, ecx=m.manager), 106)


class AllocatorTests(unittest.TestCase):
    # (allocator, its argument count, the record initialiser it calls, that
    # initialiser's stack arguments in bytes)
    ALLOCATORS = ((0x45F0B0, 14, 0x456120, 0x38), (0x45F1D0, 1, 0x4566E0, 4), (0x45F2D0, 1, 0x4566E0, 4))

    def _allocate(self, m: Machine, allocator) -> int:
        address, nargs, creator, pop = allocator
        m.created = []
        if creator not in m.stubs:
            m.stub(creator, lambda mm: (mm.created.append(mm.reg("ecx")) or 0, pop))
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

    def test_last_slot_and_never_padding(self):
        for allocator in self.ALLOCATORS:
            with self.subTest(allocator=hex(allocator[0])):
                m = Machine(render("collection_progression", True))
                for i in range(255):
                    m.villager(i)
                self.assertEqual(self._allocate(m, allocator), 255)
                m.villager(255)
                # 256..259 are zero (inactive) records; they must not be handed out
                self.assertEqual(self._allocate(m, allocator), 0xFFFFFFFF)


class RecordRoutineTests(unittest.TestCase):
    def test_index_validator(self):
        for label, image in images():
            m = Machine(image)
            for i in range(m.slots):
                m.villager(i)
            for index in (-1, 0, 149, 150, 255, 256, 259):
                with self.subTest(image=label, index=index):
                    expected = 0 <= index < m.slots
                    self.assertEqual(m.call(0x45EE60, [index & 0xFFFFFFFF], ecx=m.manager) & 0xFF,
                                     int(expected))

    def test_cure_all_reaches_every_slot(self):
        for label, image in images():
            m = Machine(image)
            for i in range(m.slots):
                m.villager(i)
                m.put8(m.rec(i) + 0xE89, 1)
            for i in range(m.slots, m.records):
                m.put8(m.rec(i) + 0xE89, 1)        # padding: inactive, never touched
            m.call(0x45D7D0, ecx=m.manager)
            with self.subTest(image=label):
                self.assertEqual([m.u8(m.rec(i) + 0xE89) for i in range(m.slots)], [0] * m.slots)
                self.assertEqual([m.u8(m.rec(i) + 0xE89) for i in range(m.slots, m.records)],
                                 [1] * (m.records - m.slots))

    def test_static_constructor_builds_every_physical_record(self):
        for label, image in images():
            m = Machine(image)
            m.call(0x47B130)
            with self.subTest(image=label):
                self.assertEqual(m.u32(m.manager), 0x49E710)              # vtable
                # the record constructor sets +0xFB4..+0xFBC to -1
                built = [m.u32(m.rec(i) + 0xFB4) for i in range(m.records + 1)]
                self.assertEqual(built[: m.records], [0xFFFFFFFF] * m.records)
                if m.slots == 256:
                    self.assertEqual(built[m.records], 0)                 # nothing past 260
                    self.assertEqual(m.records, 260)

    def test_initialiser_numbers_every_slot(self):
        for label, image in images():
            m = Machine(image)
            m.standard_stubs()
            m.call(0x45EEC0, ecx=m.manager)
            with self.subTest(image=label):
                self.assertEqual([m.u32(m.rec(i) + 0xEDC) for i in range(m.slots)], list(range(m.slots)))
                if m.slots == 256:
                    self.assertEqual([m.u32(m.rec(i) + 0xEDC) for i in range(256, 260)], [0] * 4)


def _save(image: bytes, occupied: list[int], *, canary: bool = True) -> tuple[bytes, Machine]:
    """Run the game's own save code for a village whose occupied slots are
    `occupied`; return the file the stock file writer would have written."""
    m = Machine(image)
    m.standard_stubs()
    if canary:
        m.put32(m.game + STOCK_TAIL_BLOCK, 0x2AD)    # the size dword the stock loader checks
    for k, i in enumerate(occupied):
        r = m.villager(i, age=100 + k)
        m.put32(r + 0xFB4, 0x10000 + i)              # packed into the compact entry +0x104
        m.put32(r + 0xFC0, 0x20000 + i)              # packed into the compact entry +0x110
    written = {}

    def writer(mm: Machine) -> tuple[int, int]:
        buffer, size, slot = mm.arg(0), mm.arg(1), mm.arg(2)
        written["payload"] = mm.read(buffer, size)
        written["slot"] = slot
        return 1, 12

    m.stub(0x403530, writer)
    m.stub(0x455DD0, lambda mm: (0, 0))             # flushes the record's action queue
    m.call(0x45EF80, [m.game + COMPACT_IN_GAME], ecx=m.manager)
    # the tail of 0x427C60 from `test esi, esi`: (saved edi, saved esi, return, arg)
    esp = STACK_TOP - 0x20000
    m.write(esp, struct.pack("<IIII", 0, 0, 0x0F000000, SAVE_SLOT))
    m.set_reg("esi", m.game)
    m.set_reg("edi", SAVE_SLOT)
    m.run_until(0x427D5C, 0x0F000000, esp=esp)
    assert written["slot"] == SAVE_SLOT
    payload = written["payload"]
    header = b"ldwg" + struct.pack("<II", 0x5D1D90F2, len(payload))
    return header + payload, m


def _load(image: bytes, file: bytes) -> Machine:
    """Run the game's own slot loader up to the compact-table read, then the
    compact-table read itself."""
    m = Machine(image)
    m.standard_stubs()

    def reader(mm: Machine) -> tuple[int, int]:
        buffer, size = mm.arg(0), mm.arg(1)
        if file[:4] != b"ldwg" or struct.unpack_from("<I", file, 8)[0] != size:
            return 0, 12
        mm.write(buffer, file[12 : 12 + size])
        return 1, 12

    m.stub(0x4033A0, reader)
    esp = STACK_TOP - 0x100000
    m.set_reg("ebx", m.game)
    m.set_reg("esi", SAVE_SLOT)
    m.run_until(0x42892D, 0x428975, esp=esp)        # through the copy into the game object
    m.loaded = m.call(0x45C860, [m.game + COMPACT_IN_GAME], ecx=m.manager)
    return m


def _villagers(m: Machine) -> list[tuple[int, int]]:
    return [
        (m.u32(m.rec(i) + 0xFB4), m.u32(m.rec(i) + 0xFC0))
        for i in range(m.slots)
        if m.u8(m.rec(i) + 0xF10)
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
                    self.assertEqual(len(old), 12 + STOCK_PAYLOAD)
                    self.assertEqual(len(new), 12 + PAYLOAD_256)
                    self.assertEqual(new[12 : 12 + STOCK_PAYLOAD], old[12:])
                    # 149 villagers or fewer: nothing in the extension
                    self.assertEqual(new[12 + STOCK_PAYLOAD :], bytes(PAYLOAD_256 - STOCK_PAYLOAD))

    def test_round_trip(self):
        for mode in MODES:
            image = render(mode, True)
            for n in COUNTS:
                for layout in ("packed", "scattered"):
                    occupied = list(range(n)) if layout == "packed" else list(range(256 - n, 256))
                    with self.subTest(mode=mode, villagers=n, layout=layout):
                        file, saver = _save(image, occupied)
                        self.assertEqual(saver.u32(saver.game + STOCK_TAIL_BLOCK), 0x2AD)
                        loaded = _load(image, file)
                        self.assertEqual(loaded.loaded & 0xFF, 1)
                        # villagers come back renumbered from 0, in slot order
                        self.assertEqual(_villagers(loaded), [(0x10000 + i, 0x20000 + i) for i in occupied])
                        self.assertEqual([loaded.u8(loaded.rec(i) + 0xF10) for i in range(n)], [1] * n)
                        self.assertEqual(loaded.call(0x45E8F0, ecx=loaded.manager), n)
                        self.assertEqual(loaded.u32(loaded.game + STOCK_TAIL_BLOCK), 0x2AD)

    def test_old_150_slot_save_loads_and_upgrades(self):
        stock = render("collection_progression", False)
        for mode in MODES:
            image = render(mode, True)
            for n in (0, 1, 100, 149):
                with self.subTest(mode=mode, villagers=n):
                    old, _ = _save(stock, list(range(n)))
                    loaded = _load(image, old)
                    self.assertEqual(_villagers(loaded), [(0x10000 + i, 0x20000 + i) for i in range(n)])
                    # saved again: the 256 format, and it loads back the same
                    again, _ = _save(image, list(range(n)))
                    self.assertEqual(len(again), 12 + PAYLOAD_256)
                    self.assertEqual(_villagers(_load(image, again)), _villagers(loaded))

    def test_a_256_save_is_refused_by_a_stock_build(self):
        file, _ = _save(render("collection_progression", True), list(range(10)))
        m = Machine(render("collection_progression", False))
        m.standard_stubs()
        m.stub(0x4033A0, lambda mm: (int(struct.unpack_from("<I", file, 8)[0] == mm.arg(1)), 12))
        m.set_reg("ebx", m.game)
        m.set_reg("esi", SAVE_SLOT)
        m.run_until(0x42892D, 0x428A74, esp=STACK_TOP - 0x100000)   # the stock load-failed exit

    def test_exactly_150_no_longer_overwrites_the_next_block(self):
        stock = render("collection_progression", False)
        _, saver = _save(stock, list(range(150)))
        # the stock defect this patch does not carry: the terminator lands on
        # the 0x594990 block's size dword
        self.assertNotEqual(saver.u32(saver.game + STOCK_TAIL_BLOCK), 0x2AD)
        _, saver = _save(render("collection_progression", True), list(range(150)))
        self.assertEqual(saver.u32(saver.game + STOCK_TAIL_BLOCK), 0x2AD)


FIX = "vv3_fix_vanilla_bugs"
FIX_WRITER, FIX_READER, FIX_CHECK = 0x5EFC5, 0x5C88D, 0x35710
BLOCK_CHECK, BLOCK_OBJECT = 0x435710, 0x594990


def _render_ids(mode: str, ids: list[str]) -> tuple[bytes, list[dict]]:
    from vv3_population_256_harness import EXE

    build = next(b for b in vfp.load_builds() if b.id == "vv3")
    data, applied = vfp.render_patched_bytes(EXE, build, mode, ids)
    return bytes(data), applied


def _check_block(m: Machine) -> int:
    """The progress block's size check 0x435710 on the block the load put
    right after the stock compact table."""
    return m.call(BLOCK_CHECK, [m.game + STOCK_TAIL_BLOCK], ecx=BLOCK_OBJECT) & 0xFF


class FixVanillaBugsTests(unittest.TestCase):
    """Fix Vanilla Bugs' exactly-150 rows with 256 Villagers.

    Its save-writer and loader rows fix the very routines 256 Villagers
    replaces (the end flag now lives in the 257-entry table), so with 256
    selected they stand aside (`yield_to`) and the 256 rows go onto the stock
    bytes.  Its block-check row stays: it is what lets a save the unfixed
    game already damaged (150 villagers, the 0x594990 block's size 0x2AD
    stored as 0x200) load with all 150, in the 256 build as in the 150 one."""

    def test_writer_and_reader_rows_yield_the_block_check_stays(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                _, applied = _render_ids(mode, ["vv3_population_256", FIX])
                fix_rows = {int(a["offset"], 0) for a in applied if a.get("owner") == f"feature:{FIX}"}
                self.assertNotIn(FIX_WRITER, fix_rows)
                self.assertNotIn(FIX_READER, fix_rows)
                self.assertIn(FIX_CHECK, fix_rows)
                # without 256 every row applies, unchanged
                _, applied = _render_ids(mode, [FIX])
                fix_rows = {int(a["offset"], 0) for a in applied if a.get("owner") == f"feature:{FIX}"}
                self.assertTrue({FIX_WRITER, FIX_READER, FIX_CHECK} <= fix_rows)

    def test_a_save_the_unfixed_game_damaged_loads_with_all_150(self):
        damaged, saver = _save(render("collection_progression", False), list(range(150)))
        self.assertEqual(saver.u32(saver.game + STOCK_TAIL_BLOCK), 0x200)   # the stock defect
        for mode in MODES:
            image, _ = _render_ids(mode, ["vv3_population_256", FIX])
            with self.subTest(mode=mode):
                loaded = _load(image, damaged)
                self.assertEqual(loaded.u32(loaded.game + STOCK_TAIL_BLOCK), 0x200)
                self.assertEqual(_check_block(loaded), 1)
                self.assertEqual(_villagers(loaded), [(0x10000 + i, 0x20000 + i) for i in range(150)])
                self.assertEqual(loaded.call(0x45E8F0, ecx=loaded.manager), 150)
                # saved again by this build: the size is intact and all 150 come back
                again, resaver = _save(image, list(range(150)))
                self.assertEqual(resaver.u32(resaver.game + STOCK_TAIL_BLOCK), 0x2AD)
                self.assertEqual(len(again), 12 + PAYLOAD_256)
                reloaded = _load(image, again)
                self.assertEqual(_check_block(reloaded), 1)
                self.assertEqual(_villagers(reloaded), _villagers(loaded))
        # without the fix, the 256 build refuses the damaged save like the base game
        alone = _load(render("collection_progression", True), damaged)
        self.assertEqual(_check_block(alone), 0)

    def test_exactly_150_and_256_round_trip_with_the_fix(self):
        for mode in MODES:
            image, _ = _render_ids(mode, ["vv3_population_256", FIX])
            for occupied in (list(range(149)), list(range(150)), list(range(151)), list(range(256))):
                with self.subTest(mode=mode, villagers=len(occupied)):
                    file, saver = _save(image, occupied)
                    self.assertEqual(saver.u32(saver.game + STOCK_TAIL_BLOCK), 0x2AD)
                    loaded = _load(image, file)
                    self.assertEqual(_check_block(loaded), 1)
                    self.assertEqual(_villagers(loaded), [(0x10000 + i, 0x20000 + i) for i in occupied])

    def test_a_yield_that_replaces_nothing_is_refused(self):
        build = next(b for b in vfp.load_builds() if b.id == "vv3")
        fix = vfp.get_fun_patch(FIX)
        spec = vfp._population_256_spec(build, [vfp.get_fun_patch("vv3_population_256")])
        row = dict(next(p for p in fix.patches if int(p["offset"], 0) == FIX_CHECK),
                   yield_to={"feature": "vv3_population_256"})
        with self.assertRaises(vfp.PatcherError):
            vfp._fun_row_yields(fix, row, spec, [fix, vfp.get_fun_patch("vv3_population_256")])


# ---- every other widened routine, against stock ------------------------
#
# (routine, its arguments, what it returns).  An argument "rec:k" is villager
# k's record, "idx:k" villager k's index and "out" a dword to write to.
# Returns: "index" (a slot or -1), "pointer" (a record address or 0),
# "value" (compared as is), "bool" (AL) or "none" (EAX is left over; only the
# effects are compared).
DIFFERENTIAL = {
    0x45C9D0: ([1], "index"), 0x45CBC0: ([0, 1], "index"), 0x45CE00: (["rec:3"], "index"),
    0x45D2C0: ([1], "index"), 0x45D460: ([1, 0, 0, 0], "pointer"),
    0x45DCE0: ([0, 0, 0, 0, 0], "none"), 0x45DDE0: ([0, 0, 0, 0, 0], "none"),
    0x45E0F0: ([0, 0, 0, 0, 0, 0], "none"), 0x45E370: ([0, 0, 0, 0, 0, 0, 0, 0], "none"),
    0x45E610: ([0, 0, 0, 0, 0, 0], "none"), 0x45ECB0: ([2, 0, "out"], "pointer"),
    0x45FB20: ([], "bool"), 0x45F960: ([500, 500, 0], "pointer"), 0x45FA30: ([500, 500, 0], "pointer"),
    0x460D20: ([500, 500], "value"), 0x45C900: (["idx:3"], "none"), 0x45C950: ([], "index"),
    0x45D240: ([0], "index"), 0x45EBF0: ([2], "bool"), 0x45EF00: ([], "pointer"),
    0x45EF30: ([], "pointer"), 0x45F890: ([500, 500, 0, 0], "pointer"), 0x45FC10: ([], "value"),
    0x45FAD0: ([], "none"), 0x45FCF0: ([0], "none"), 0x45F640: ([], "none"),
    0x45D760: ([30, 1, 5], "none"), 0x45D8D0: ([], "none"), 0x45D920: ([30, 5], "none"),
    0x45D990: ([30], "none"), 0x45D9F0: ([30], "none"), 0x45DC40: ([30, 5], "none"),
    0x45EC30: ([], "none"), 0x45FCC0: ([], "none"),
}
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
    m.put8(r + 0xF10, 1)
    m.put8(r + 0xF11, 0)
    m.put8(r + 0xF12, 0)
    m.put32(r + 0xE78, rnd.choice((0, 30, 60, 90, 100)))
    m.put32(r + 0xEDC, slot)


def _differential_run(image: bytes, fn: int, args, slots, shift: int):
    m = Machine(image)
    rolls = random.Random(7)
    m.standard_stubs(lambda n: rolls.randrange(1 << 30))
    for slot in slots:
        _fill(m, slot, 1000 + slot - shift)
    out = m.alloc(4)
    real = []
    for a in args:
        if isinstance(a, str) and a.startswith("rec:"):
            real.append(m.rec(int(a[4:]) + shift))
        elif isinstance(a, str) and a.startswith("idx:"):
            real.append(int(a[4:]) + shift)
        elif a == "out":
            real.append(out)
        else:
            real.append(a)
    eax = m.call(fn, real, ecx=m.manager, limit=50_000_000)
    records = m.read(m.rec(shift), STRIDE * len(slots)) if slots else b""
    return m, eax, list(m.rng_calls), records


class DifferentialTests(unittest.TestCase):
    """Each widened routine, run on the stock executable and on 256 with the
    same villagers: in the same slots (0..36 and 0..149), and moved up by 106
    to slots 106..255, the top of the 256 table.  The result, the random rolls
    asked for and every byte of every villager must agree -- the moved run
    maps indices and record addresses by +106."""

    def _check(self, fn: int, stock: bytes, image: bytes, n: int, shift: int) -> None:
        args, kind = DIFFERENTIAL[fn]
        ms, es, rs, recs_s = _differential_run(stock, fn, args, list(range(n)), 0)
        mp, ep, rp, recs_p = _differential_run(image, fn, args, list(range(shift, shift + n)), shift)
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
        for k in range(n):
            a = bytearray(recs_s[k * STRIDE : (k + 1) * STRIDE])
            b = bytearray(recs_p[k * STRIDE : (k + 1) * STRIDE])
            # the own-index field holds the slot, which the move changes
            if struct.unpack_from("<I", a, 0xEDC)[0] == k and struct.unpack_from("<I", b, 0xEDC)[0] == k + shift:
                b[0xEDC : 0xEDC + 4] = a[0xEDC : 0xEDC + 4]
            self.assertEqual(bytes(b), bytes(a), f"villager {k} differs")

    def test_same_slots_and_top_slots(self):
        stock = render("collection_progression", False)
        image = render("collection_progression", True)
        for fn in DIFFERENTIAL:
            for n, shift in ((37, 0), (150, 0), (150, SHIFT)):
                with self.subTest(routine=hex(fn), villagers=n, first_slot=shift):
                    self._check(fn, stock, image, n, shift)


class VisitorTests(unittest.TestCase):
    """Loops over every slot that hand each record to another routine: that
    routine sees all 256 slots, in order, and none of the padding."""

    VISITORS = (
        # (loop, its arguments, the per-record routine (record in ECX), its pops)
        (0x45C8D0, [], 0x456000, 0),
        (0x45C990, [], 0x45C360, 4),
        (0x45F3B0, [], 0x456E90, 0),
    )

    def test_every_slot_is_visited(self):
        for label, image in images():
            for loop, args, callee, pop in self.VISITORS:
                with self.subTest(image=label, loop=hex(loop)):
                    m = Machine(image)
                    m.standard_stubs()
                    for i in range(m.records):
                        m.villager(i)          # padding too: it must still be skipped
                    seen = []
                    m.stub(callee, lambda mm: (seen.append(mm.reg("ecx")) or 0, pop))
                    m.call(loop, args, ecx=m.manager)
                    self.assertEqual(seen, [m.rec(i) for i in range(m.slots)])


def _layout() -> dict:
    feature = next(p for p in vfp.load_fun_patches() if p.id == "vv3_population_256")
    return feature.raw["population_256"]["layout"]


class DetailsScreenTests(unittest.TestCase):
    """The Villager Details screen keeps the living villagers in a list it
    builds, sorts, and walks with Previous / Next.  With 256 villagers the
    stock 150-entry list inside the screen object would overflow into the
    count after it; the 256 build keeps the list in its own 256-entry buffer."""

    NEXT, PREVIOUS = 4, 3

    def _screen(self, image: bytes, slots: list[int]) -> tuple[Machine, int]:
        m = Machine(image)
        m.standard_stubs()
        for k, i in enumerate(slots):
            m.villager(i, age=1000 + 7 * ((k * 37) % len(slots)))   # distinct ages, shuffled
        screen = m.alloc(0x400)
        m.put32(screen + 0x264, 0)          # sort by age
        m.put32(screen + 0x268, 0)
        m.put32(screen + 0x2BC, 1)
        m.put32(screen + 0x2C0, self.PREVIOUS)
        m.put32(screen + 0x2C4, self.NEXT)
        m.put32(screen + 0x308, m.alloc(0x100))
        m.put32(screen + 0x33C, 0x5A5A5A5A)  # just past the stock object: never written
        for va, pop in ((0x40D1E0, 8), (0x40D1A0, 4), (0x42E200, 4), (0x424110, 4)):
            m.stub(va, lambda mm, p=pop: (0, p))
        m.stub(0x46F780, lambda mm: (0, 0))
        m.call(0x46E280, ecx=screen)
        m.call(0x46E390, ecx=screen)
        return m, screen

    def _list(self, m: Machine, screen: int) -> list[int]:
        base = int(_layout()["details_list"], 0) if m.slots == 256 else screen + 8
        return [m.u32(base + 4 * k) for k in range(m.u32(screen + 0x260))]

    def test_list_holds_every_living_villager_in_order(self):
        for label, image in images():
            for n in COUNTS:
                probe = Machine(image)
                if n > probe.slots:
                    continue
                with self.subTest(image=label, villagers=n):
                    slots = list(range(probe.slots - n, probe.slots))   # the top slots
                    m, screen = self._screen(image, slots)
                    listed = self._list(m, screen)
                    self.assertEqual(sorted(listed), slots)
                    ages = [m.u32(m.rec(i) + 0xDC4) for i in listed]
                    self.assertEqual(ages, sorted(ages))
                    self.assertEqual(m.u32(screen + 0x33C), 0x5A5A5A5A)

    def test_same_order_as_stock(self):
        stock = render("collection_progression", False)
        image = render("collection_progression", True)
        for n in (0, 1, 37, 149, 150):
            with self.subTest(villagers=n):
                ms, ss = self._screen(stock, list(range(n)))
                mp, sp = self._screen(image, list(range(n)))
                self.assertEqual(self._list(mp, sp), self._list(ms, ss))

    def test_previous_and_next_walk_the_whole_list(self):
        for label, image in images():
            m, screen = self._screen(image, list(range(Machine(image).slots)))
            listed = self._list(m, screen)
            with self.subTest(image=label):
                for start, button, expected in (
                    (148, self.NEXT, 149), (149, self.NEXT, 150 % len(listed)),
                    (len(listed) - 1, self.NEXT, 0), (0, self.PREVIOUS, len(listed) - 1),
                    (len(listed) - 1, self.PREVIOUS, len(listed) - 2),
                ):
                    m.put32(m.game + 0x12FC0, listed[start])
                    self.assertEqual(m.call(0x46CB20, [listed[start]], ecx=screen), start)
                    m.call(0x46E530, [8, button], ecx=screen)
                    self.assertEqual(m.u32(m.game + 0x12FC0), listed[expected])
                    self.assertEqual(m.u8(m.rec(listed[expected]) + 0xF11), 1)    # selected


class SpriteHandleTests(unittest.TestCase):
    def test_handles_stay_at_their_stock_addresses(self):
        """The fourteen sprite handles after the last stock record keep their
        stock addresses: 31 absolute reads elsewhere expect them there."""
        for label, image in images():
            m = Machine(image)
            m.stub(0x42E9D0, lambda mm: (0x1234, 0))
            m.stub(0x42E8A0, lambda mm: (0x7000 + mm.arg(0), 4))
            m.stub(0x42EB80, lambda mm: (0x7000 + mm.arg(0), 4))
            m.call(0x45C730, ecx=m.manager)
            handles = [m.u32(0x6C5D2C + 4 * k) for k in range(14)]
            with self.subTest(image=label):
                self.assertTrue(all(0x7000 <= h < 0x7100 for h in handles), [hex(h) for h in handles])
                if m.slots == 256:
                    # nothing was written into the relocated table
                    self.assertEqual(m.read(m.rec(150), 0x40), bytes(0x40))


class PopulationCapTests(unittest.TestCase):
    """The cap check 0x45FE30 in every mode, with every combination of
    collections and Magic Level, and all three huts built."""

    def _cap(self, image: bytes, collections: int, magic: int) -> int:
        lo, hi = 0, 300
        while lo < hi:                     # the smallest population refused
            n = (lo + hi) // 2
            m = Machine(image)
            for i in range(min(n, m.slots)):
                m.villager(i)
            extra = n - min(n, m.slots)
            if extra:                      # pending babies stand for the rest
                m.put32(m.rec(0) + 0xE8C, 1)
                m.put32(m.rec(0) + 0xE90, extra)
            found = {0x34: collections > 0, 0x40: collections > 1, 0x4C: collections > 2, 0x58: collections > 3}
            m.stub(0x42DE40, lambda mm: (int(found[mm.arg(0)]), 4))
            m.stub(0x426FC0, lambda mm: (magic, 4))
            m.stub(0x4321F0, lambda mm: (1, 4))
            if m.call(0x45FE30, ecx=m.manager) & 0xFF:
                lo = n + 1
            else:
                hi = n
        return lo

    def test_caps(self):
        bonus = {0: 0, 1: 5, 2: 10, 3: 15, 4: 25}
        for collections in (0, 2, 4):
            for magic in (0, 3):
                extra = bonus[collections] + (10 if magic >= 3 else 0)
                for mode, with_256, expected in (
                    ("stock", False, 90 + extra), ("stock", True, 90 + extra),
                    ("collection_progression", False, 115 + extra),
                    ("collection_progression", True, 221 + extra),
                    ("immediate_fixed", False, 150), ("immediate_fixed", True, 256),
                ):
                    with self.subTest(mode=mode, with_256=with_256, collections=collections, magic=magic):
                        self.assertEqual(self._cap(render(mode, with_256), collections, magic), expected)


class SlotSafetyTests(unittest.TestCase):
    def test_occupied_slot_counter(self):
        """The automatic safety layer's slot counter (0x47B318) walks the
        relocated table and counts the active BYTE: a free record whose
        selected/held bytes are stale is free."""
        for mode in MODES:
            for n in COUNTS:
                with self.subTest(mode=mode, occupied=n):
                    m = Machine(render(mode, True))
                    for i in range(n):
                        m.villager(i)
                    for i in range(n, 256):
                        m.put8(m.rec(i) + 0xF11, 1)
                        m.put8(m.rec(i) + 0xF12, 1)
                    self.assertEqual(m.call(0x47B318), n)

    def test_guards_compare_against_256(self):
        image = render("collection_progression", True)
        m = Machine(image)
        self.assertEqual(m.read(0x47B265, 5), bytes.fromhex("3DFD000000"))   # triplets: 3 free
        self.assertEqual(m.read(0x47B285, 5), bytes.fromhex("3DFE000000"))   # twins: 2 free
        self.assertEqual(m.read(0x47B2E5, 5), bytes.fromhex("3D00010000"))   # event newcomer
        self.assertEqual(m.read(0x47B305, 5), bytes.fromhex("3D00010000"))   # barrel child


class OriginsCompanionTests(unittest.TestCase):
    """The Origins companion (the DLL that runs the Tech-menu upgrades) reads
    the manager from 0x4279B3 and the cap's base from 0x45FEE1, so the
    Barrel of Babies check answers for the 256 build in every mode."""

    DLL = vfp.ROOT / "data" / "candidates" / "VVFP VV3 Safe Upgrades.dll"

    def _room(self, mode: str, with_256: bool, villagers: int, *, collections: int = 0,
              magic: int = 0) -> int:
        from story_emulator import Process

        proc = Process(render(mode, with_256), self.DLL)
        stride, manager = STRIDE, struct.unpack("<I", proc.read(0x4279B4, 4))[0]
        for i in range(villagers):
            record = manager + 0x14 + i * stride
            proc.write(record + 0xF10, b"\x01")
            proc.put32(record + 0xE78, 50)
        found = {0x34: collections > 0, 0x40: collections > 1, 0x4C: collections > 2, 0x58: collections > 3}
        proc.stub(0x42DE40, lambda p: (int(found[p.arg(0)]), 4))
        proc.stub(0x426FC0, lambda p: (magic, 4))
        return proc.export("PrepareBarrelBabies") & 0xFF

    def test_barrel_room_follows_the_mode_and_the_table(self):
        """No Population Increase computes the live cap (90 + bonuses); the
        modes that raise it are limited by the physical record table, as the
        150-slot build already was -- 256 records in the 256 build."""
        cases = (
            # mode, 256, villagers, room for three more
            ("stock", True, 87, 1), ("stock", True, 88, 0),
            ("collection_progression", True, 253, 1), ("collection_progression", True, 254, 0),
            ("collection_progression", False, 147, 1), ("collection_progression", False, 148, 0),
            ("immediate_fixed", True, 253, 1), ("immediate_fixed", True, 254, 0),
            ("immediate_fixed", False, 147, 1), ("immediate_fixed", False, 148, 0),
        )
        for mode, with_256, n, expected in cases:
            with self.subTest(mode=mode, with_256=with_256, villagers=n):
                self.assertEqual(self._room(mode, with_256, n), expected)
        with self.subTest("No Population Increase, every bonus"):
            self.assertEqual(self._room("stock", True, 122, collections=4, magic=3), 1)
            self.assertEqual(self._room("stock", True, 123, collections=4, magic=3), 0)


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
    """Instructions in any patch's own code that still name the stock table,
    or the withdrawn layout's +0x7598 probe."""
    from capstone import CS_ARCH_X86, CS_MODE_32, CS_OP_IMM, CS_OP_MEM, Cs

    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    found = []
    for item in applied:
        owner = item.get("owner", "")
        offset = int(item["offset"], 0)
        if not item.get("after") or offset < 0x1000 or owner.endswith("vv3_population_256"):
            continue
        va = vfp._virtual_address_for_offset(data, offset)
        if va is None:
            continue
        blob = data[offset : offset + len(item["after"]) // 2]
        for insn in md.disasm(blob, int(va, 16)):
            for op in insn.operands:
                value = None
                if op.type == CS_OP_IMM:
                    value = op.imm & 0xFFFFFFFF
                elif op.type == CS_OP_MEM:
                    value = op.mem.disp & 0xFFFFFFFF
                if value is not None and (0x59E110 <= value < 0x6C5D2C or value == 0x7598):
                    found.append(f"{owner} 0x{insn.address:X} {insn.mnemonic} {insn.op_str}")
    return found


class CompositionTests(unittest.TestCase):
    """256 Villagers with every public VV3 patch: alone with each (and its
    prerequisites), all at once, and all that do not pull in Origins, in
    every mode.  Each renders, and no patch's own code is left naming the
    stock table."""

    def _render(self, mode: str, ids: list[str]) -> tuple[bytes, list[dict]]:
        build = next(b for b in vfp.load_builds() if b.id == "vv3")
        from vv3_population_256_harness import EXE

        data, applied = vfp.render_patched_bytes(EXE, build, mode, ["vv3_population_256", *ids])
        return bytes(data), applied

    def test_every_public_patch(self):
        public = [p.id for p in vfp.load_public_fun_patches()
                  if p.raw.get("game_id") == "vv3" and p.id != "vv3_population_256"]
        origins = {"vv3_enable_origins_exclusive_features"}
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

    def test_output_is_named_for_its_own_save_folder(self):
        build = next(b for b in vfp.load_builds() if b.id == "vv3")
        with_256 = [vfp.get_fun_patch("vv3_population_256")]
        self.assertEqual(vfp._output_name(build, "collection_progression", with_256),
                         "Virtual Villagers - The Secret City - Modded 256.exe")
        self.assertEqual(vfp._output_name(build, "collection_progression", []),
                         "Virtual Villagers - The Secret City - Modded.exe")
        self.assertEqual(vfp.output_folder_for(vfp.ROOT / "x" / "game.exe", build, "stock", with_256,
                                               output_root=vfp.ROOT).name,
                         "Virtual Villagers - The Secret City - Modded 256")


if __name__ == "__main__":
    unittest.main()
