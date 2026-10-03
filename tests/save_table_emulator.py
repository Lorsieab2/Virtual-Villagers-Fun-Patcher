"""Unicorn harness for the saved-villager table of The Secret City (VV3) and The Tree of Life (VV4).

Both games save their villagers the same way.  On save, the manager's writer packs every active
villager (VV4: not a ghost either), in record order, into a table of 150 fixed-size entries inside
the game-state object, then writes a 0 "end of list" flag at entry[count].  On load, the loader
resets all 150 records and unpacks entries until it meets a 0 flag.  Directly after the 150-entry
table the game state holds the progress block, whose first dword is its size; that block is saved
just BEFORE the villagers and checked on load (stored size must equal the computed size).

With exactly 150 villagers the stock writer's end flag lands on the low byte of that size
(VV4 0x250 -> 0x200, VV3 0x2AD -> 0x200), so the block check rejects the save.  The stock loader
has no count limit either, so an intact 150-entry table would be read past its end.

This harness runs the REAL writer, loader, per-villager (de)serialisers and block check from a
rendered executable.  Only these are stubbed: the game-state getter (returns our state buffer),
the writer's per-villager pre-save hook (a no-op here), the record reset (zeroes the record) and
the block's size computation (VV4: the 0x250 the game computes from its sub-objects; VV3: the
game's own `mov eax, 0x2AD; ret` at 0x435700), so a test can also make it exceed 0x1000.  The block's sub-object table is empty in a fresh image, so the check copies
its 0xD0-byte header and returns.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX,
    UC_X86_REG_EDI, UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP,
)


@dataclass(frozen=True)
class Layout:
    manager: int
    first_record: int
    stride: int
    active: int                 # active-flag byte in the record
    ghost: int | None           # VV4: a ghost (+0x1CC7) is active but never saved
    table: int                  # saved table offset in the game state
    entry: int                  # saved entry size
    block: int                  # progress block offset in the game state (= table + 150 * entry)
    block_this: int             # the progress block's object (ECX of the block check)
    block_size: int             # the size the game computes for it
    writer: int
    loader: int
    check: int
    state_getter: int
    pre_save: int               # per-villager hook the writer calls before packing
    reset: int                  # per-record reset the loader calls 150 times
    deserialise: int
    size_fn: int                # the block's size computation (stubbed)
    # persisted record fields: (record offset, size) -- what one saved entry carries
    persisted: tuple[tuple[int, int], ...]


VV4 = Layout(
    manager=0x50E568, first_record=0x50E5AC, stride=0x2E3C, active=0x1CC4, ghost=0x1CC7,
    table=0xC868, entry=0x104, block=0x160C0, block_this=0x4D8BF8, block_size=0x250,
    writer=0x4660A0, loader=0x466110, check=0x4387A0, state_getter=0x41FE70, pre_save=0x45EAA0,
    reset=0x45D8A0, deserialise=0x45DBE0, size_fn=0x438770,
    persisted=((0x1B8C, 0xA8), (0x1C34, 0x28), (0x1C5C, 0x18), (0x1E60, 0x18)),
)
VV3 = Layout(
    manager=0x59E110, first_record=0x59E124, stride=0x1F8C, active=0xF10, ghost=None,
    table=0x786C, entry=0x11C, block=0x11ED4, block_this=0x594990, block_size=0x2AD,
    writer=0x45EF80, loader=0x45C860, check=0x435710, state_getter=0x428B60, pre_save=0x455DD0,
    reset=0x456000, deserialise=0x456830, size_fn=0x435700,
    persisted=((0xDC4, 0xA8), (0xE6C, 0x40), (0xEAC, 0x18), (0xFB4, 0xC), (0xFC0, 0xC)),
)
assert VV4.table + 150 * VV4.entry == VV4.block
assert VV3.table + 150 * VV3.entry == VV3.block

STATE = 0x30000000
STATE_SIZE = 0x20000
STACK = 0x70000000
RETURN = 0x0BAD0000


class Machine:
    def __init__(self, exe: bytes, layout: Layout) -> None:
        self.layout = layout
        pe = pefile.PE(data=exe)
        image = pe.get_memory_mapped_image()
        size = max(len(image), pe.OPTIONAL_HEADER.SizeOfImage)
        self.mu = mu = Uc(UC_ARCH_X86, UC_MODE_32)
        mu.mem_map(0x400000, (size + 0xFFFF) & ~0xFFFF)
        mu.mem_write(0x400000, image)
        mu.mem_map(STATE, STATE_SIZE)
        mu.mem_map(STACK - 0x10000, 0x20000)
        mu.mem_map(RETURN, 0x1000)
        self.deserialised = 0
        self.computed_size = layout.block_size
        mu.hook_add(UC_HOOK_CODE, self._on_code)

    # -- stubs -------------------------------------------------------------------------
    def _on_code(self, mu, address, size, user_data) -> None:
        lay = self.layout
        if address == lay.state_getter:
            self._return(STATE, 0)
        elif address == lay.pre_save:
            self._return(0, 0)
        elif address == lay.reset:
            ecx = mu.reg_read(UC_X86_REG_ECX)
            mu.mem_write(ecx, b"\0" * lay.stride)
            self._return(0, 0)
        elif address == lay.size_fn:
            self._return(self.computed_size, 0)
        elif address == lay.deserialise:
            self.deserialised += 1          # counted, then the real routine runs

    def _return(self, value: int, pop: int) -> None:
        mu = self.mu
        esp = mu.reg_read(UC_X86_REG_ESP)
        ret = struct.unpack("<I", mu.mem_read(esp, 4))[0]
        mu.reg_write(UC_X86_REG_EAX, value & 0xFFFFFFFF)
        mu.reg_write(UC_X86_REG_ESP, esp + 4 + pop)
        mu.reg_write(UC_X86_REG_EIP, ret)

    def thiscall(self, entry: int, this: int, *args: int) -> int:
        mu = self.mu
        esp = STACK
        for arg in reversed(args):
            esp -= 4
            mu.mem_write(esp, struct.pack("<I", arg & 0xFFFFFFFF))
        esp -= 4
        mu.mem_write(esp, struct.pack("<I", RETURN))
        mu.reg_write(UC_X86_REG_ESP, esp)
        mu.reg_write(UC_X86_REG_ECX, this)
        saved = (0x5EED0001, 0x5EED0002, 0x5EED0003, 0x5EED0004)
        for reg, value in zip((UC_X86_REG_EBX, UC_X86_REG_EBP, UC_X86_REG_EDI, UC_X86_REG_ESI), saved):
            mu.reg_write(reg, value)
        mu.emu_start(entry, RETURN, count=5_000_000)
        assert mu.reg_read(UC_X86_REG_ESP) == STACK, "callee did not pop exactly its arguments"
        assert tuple(mu.reg_read(r) for r in (UC_X86_REG_EBX, UC_X86_REG_EBP, UC_X86_REG_EDI, UC_X86_REG_ESI)) == saved
        return mu.reg_read(UC_X86_REG_EAX)

    # -- game-level helpers ----------------------------------------------------------------
    def record(self, index: int) -> int:
        return self.layout.first_record + index * self.layout.stride

    def populate(self, count: int, seed: int = 1, ghosts: tuple[int, ...] = ()) -> None:
        """Make records 0..count-1 active with distinctive persisted fields; `ghosts` are
        additionally made active ghosts (VV4)."""
        lay = self.layout
        for index in range(150):
            base = self.record(index)
            self.mu.mem_write(base, b"\0" * lay.stride)
        for index in list(range(count)) + list(ghosts):
            base = self.record(index)
            for offset, size in lay.persisted:
                data = bytes(((seed * 131 + index * 17 + offset + k) * 7) & 0xFF for k in range(size))
                self.mu.mem_write(base + offset, data)
            self.mu.mem_write(base + lay.active, b"\1")
            if lay.ghost is not None:
                self.mu.mem_write(base + lay.ghost, b"\1" if index in ghosts else b"\0")

    def persisted(self, index: int) -> bytes:
        base = self.record(index)
        return b"".join(bytes(self.mu.mem_read(base + offset, size)) for offset, size in self.layout.persisted)

    def active(self, index: int) -> int:
        return self.mu.mem_read(self.record(index) + self.layout.active, 1)[0]

    def set_block_size(self, value: int) -> None:
        self.mu.mem_write(STATE + self.layout.block, struct.pack("<I", value))

    def block_size_stored(self) -> int:
        return struct.unpack("<I", self.mu.mem_read(STATE + self.layout.block, 4))[0]

    def entry_flag(self, index: int) -> int:
        return self.mu.mem_read(STATE + self.layout.table + index * self.layout.entry, 1)[0]

    def table_bytes(self) -> bytes:
        return bytes(self.mu.mem_read(STATE + self.layout.table, 150 * self.layout.entry))

    def state_bytes(self) -> bytes:
        return bytes(self.mu.mem_read(STATE, STATE_SIZE))

    def save(self) -> int:
        return self.thiscall(self.layout.writer, self.layout.manager, STATE + self.layout.table) & 0xFF

    def load(self) -> int:
        self.deserialised = 0
        return self.thiscall(self.layout.loader, self.layout.manager, STATE + self.layout.table) & 0xFF

    def check_block(self) -> int:
        return self.thiscall(self.layout.check, self.layout.block_this, STATE + self.layout.block) & 0xFF


class SaveTableCases:
    """Mixin for a unittest.TestCase.  The subclass provides LAYOUT and `builds()` returning
    {(mode, label): exe bytes} with label "stock" (no fix) and "patched"/"patched_with_all"."""

    LAYOUT: Layout
    COUNTS = (0, 1, 2, 75, 148, 149, 150)

    def _machine(self, exe: bytes) -> Machine:
        m = Machine(exe, self.LAYOUT)
        m.set_block_size(self.LAYOUT.block_size)
        return m

    def _ghosts(self, count: int) -> tuple[int, ...]:
        # VV4: an active ghost right after the living villagers must never be saved
        return (count,) if self.LAYOUT.ghost is not None and count < 150 else ()

    def _modes(self) -> list[str]:
        return sorted({mode for mode, _ in self.builds()})

    def test_writer_never_touches_the_next_block(self) -> None:
        for (mode, label), exe in self.builds().items():
            for count in self.COUNTS:
                with self.subTest(mode=mode, build=label, count=count):
                    m = self._machine(exe)
                    m.populate(count, ghosts=self._ghosts(count))
                    self.assertEqual(m.save(), 1)
                    flags = [m.entry_flag(i) for i in range(150)]
                    self.assertEqual(flags[:count], [1] * count)
                    if count < 150:
                        self.assertEqual(flags[count], 0)       # the end-of-list flag is still written
                    if label == "stock" and count == 150:
                        # the base game's bug: the end flag zeroes the size's low byte
                        self.assertEqual(m.block_size_stored(), self.LAYOUT.block_size & ~0xFF)
                    else:
                        self.assertEqual(m.block_size_stored(), self.LAYOUT.block_size)

    def test_patched_writer_output_equals_stock_below_150(self) -> None:
        builds = self.builds()
        for mode in self._modes():
            for count in self.COUNTS:
                if count == 150:
                    continue
                with self.subTest(mode=mode, count=count):
                    outputs = {}
                    for label in ("stock", "patched", "patched_with_all"):
                        m = self._machine(builds[(mode, label)])
                        m.populate(count, seed=count + 3, ghosts=self._ghosts(count))
                        m.save()
                        outputs[label] = m.state_bytes()
                    self.assertEqual(outputs["patched"], outputs["stock"])
                    self.assertEqual(outputs["patched_with_all"], outputs["stock"])

    def test_150_differs_from_stock_only_in_the_preserved_size_byte(self) -> None:
        builds = self.builds()
        for mode in self._modes():
            with self.subTest(mode=mode):
                stock = self._machine(builds[(mode, "stock")])
                stock.populate(150, seed=9)
                stock.save()
                fixed = self._machine(builds[(mode, "patched")])
                fixed.populate(150, seed=9)
                fixed.save()
                a, b = stock.state_bytes(), fixed.state_bytes()
                diff = [i for i in range(len(a)) if a[i] != b[i]]
                self.assertEqual(diff, [self.LAYOUT.block])
                self.assertEqual(b[self.LAYOUT.block], self.LAYOUT.block_size & 0xFF)

    def test_round_trip_keeps_every_villager(self) -> None:
        for (mode, label), exe in self.builds().items():
            if label == "stock":
                continue
            for count in self.COUNTS:
                with self.subTest(mode=mode, build=label, count=count):
                    m = self._machine(exe)
                    m.populate(count, seed=count + 11, ghosts=self._ghosts(count))
                    m.save()
                    saved_state = m.state_bytes()
                    before = [m.persisted(i) for i in range(count)]
                    self.assertEqual(m.check_block(), 1)
                    m.populate(0)
                    self.assertEqual(m.load(), 1)
                    self.assertEqual(m.deserialised, count)
                    self.assertEqual([m.persisted(i) for i in range(count)], before)
                    self.assertEqual([m.active(i) for i in range(150)], [1] * count + [0] * (150 - count))
                    # saving the loaded village again writes the identical table and block size
                    m.save()
                    self.assertEqual(m.table_bytes(), saved_state[self.LAYOUT.table:self.LAYOUT.block])
                    self.assertEqual(m.block_size_stored(), self.LAYOUT.block_size)

    def test_loader_stops_after_150_entries(self) -> None:
        # A full table followed by an intact block (non-zero size byte): the base game reads a
        # 151st villager out of the block into the memory after the last record; fixed stops.
        sentinel = self.LAYOUT.first_record + 150 * self.LAYOUT.stride + self.LAYOUT.active
        for (mode, label), exe in self.builds().items():
            with self.subTest(mode=mode, build=label):
                m = self._machine(exe)
                m.populate(150, seed=5)
                m.save()
                m.set_block_size(self.LAYOUT.block_size)    # intact, whichever writer ran
                m.populate(0)
                m.mu.mem_write(sentinel, b"\0")
                m.load()
                if label == "stock":
                    self.assertEqual(m.deserialised, 151)
                    self.assertEqual(m.mu.mem_read(sentinel, 1)[0], 1)
                else:
                    self.assertEqual(m.deserialised, 150)
                    self.assertEqual(m.mu.mem_read(sentinel, 1)[0], 0)

    def test_block_check_cases(self) -> None:
        size = self.LAYOUT.block_size
        cases = [
            # stored size, last entry's flag, stock result, fixed result
            (size, 0, 1, 1),
            (size, 1, 1, 1),
            (size & ~0xFF, 1, 0, 1),            # the damaged 150-villager save: repaired
            (size & ~0xFF, 0, 0, 0),            # same size bytes without a full table: refused
            (size & ~0xFF, 2, 0, 0),            # the writer only ever stores flag 1
            (size + 1, 1, 0, 0),
            (size - 1, 1, 0, 0),
            ((size & ~0xFF) + 0x100, 1, 0, 0),  # high bytes differ
            (0, 1, 0, 0),
            (size | 0x10000, 1, 0, 0),
        ]
        for (mode, label), exe in self.builds().items():
            for stored, flag, stock_ok, fixed_ok in cases:
                with self.subTest(mode=mode, build=label, stored=hex(stored), flag=flag):
                    m = self._machine(exe)
                    m.set_block_size(stored)
                    m.mu.mem_write(STATE + self.LAYOUT.table + 149 * self.LAYOUT.entry, bytes([flag]))
                    self.assertEqual(m.check_block(), stock_ok if label == "stock" else fixed_ok)

    def test_block_check_still_refuses_an_oversized_block(self) -> None:
        # The base game's first test (computed size > 0x1000 -> refuse) is kept.
        for (mode, label), exe in self.builds().items():
            for stored in (0x1001, 0x1000 + 0x100, 0x1100):
                with self.subTest(mode=mode, build=label, stored=hex(stored)):
                    m = self._machine(exe)
                    m.computed_size = stored
                    m.set_block_size(stored)
                    m.mu.mem_write(STATE + self.LAYOUT.table + 149 * self.LAYOUT.entry, b"")
                    self.assertEqual(m.check_block(), 0)
            with self.subTest(mode=mode, build=label, stored="0x1000"):
                m = self._machine(exe)
                m.computed_size = 0x1000
                m.set_block_size(0x1000)
                self.assertEqual(m.check_block(), 1)

    def test_damaged_150_save_written_by_the_base_game_loads_with_every_villager(self) -> None:
        builds = self.builds()
        for mode in self._modes():
            stock = self._machine(builds[(mode, "stock")])
            stock.populate(150, seed=21)
            before = [stock.persisted(i) for i in range(150)]
            stock.save()
            damaged = stock.state_bytes()
            self.assertEqual(stock.check_block(), 0)               # the base game refuses it
            for label in ("patched", "patched_with_all"):
                with self.subTest(mode=mode, build=label):
                    m = self._machine(builds[(mode, label)])
                    m.mu.mem_write(STATE, damaged)
                    self.assertEqual(m.check_block(), 1)
                    m.populate(0)
                    self.assertEqual(m.load(), 1)
                    self.assertEqual(m.deserialised, 150)
                    self.assertEqual([m.persisted(i) for i in range(150)], before)
                    # the next save: the game writes the block (with its true size) and then the
                    # villagers, which now leave it intact
                    m.set_block_size(self.LAYOUT.block_size)
                    m.save()
                    self.assertEqual(m.block_size_stored(), self.LAYOUT.block_size)
                    self.assertEqual([m.entry_flag(i) for i in range(150)], [1] * 150)
