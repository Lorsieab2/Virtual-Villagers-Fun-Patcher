"""Villagers Have Last Names (all five games).

Every game carries a third list of 50 names beside its male and female first
names, which its naming routine copies and never reads (Virtual Villagers 6
and 7 later used it for last names).  "VVFP Last Names.dll" detours the
naming routine at game start; a new villager's name becomes "<first> <last>",
the last name being the family's (name number family - 1).

These tests run the SHIPPED companion and each stock executable in an
emulator: VvfpStartup installs the detour exactly as at game start (its
Windows calls answered by the harness), and then the game's own naming
routine runs through it, with the game's own rand() answering scripted
rolls.
"""
from __future__ import annotations

import hashlib
import json
import struct
import sys
import unittest
from pathlib import Path

import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX,
                               UC_X86_REG_EDI, UC_X86_REG_ESI, UC_X86_REG_ESP)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
STOCK = ROOT / "research" / "stock-executables"
DLL = ROOT / "assets" / "last_names" / "VVFP Last Names.dll"
EXE = {
    "vv1": "Virtual Villagers - A New Home.exe",
    "vv2": "Virtual Villagers - The Lost Children.exe",
    "vv3": "Virtual Villagers - The Secret City.exe",
    "vv4": "Virtual Villagers - The Tree of Life.exe",
    "vv5": "Virtual Villagers - New Believers.exe",
}
GAME_NO = {g: int(g[2]) for g in EXE}
# routine, rand(), unused list, male list, female list
SITES = {
    "vv1": (0x43B950, 0x402F10, 0x481BA0, 0x481D28, 0x481F50),
    "vv2": (0x44B710, 0x4031A0, 0x48FB98, 0x48FD20, 0x48FFC0),
    "vv3": (0x45C670, 0x4032D0, 0x49DFF8, 0x49E180, 0x49E428),
    "vv4": (0x465DA0, 0x4036D0, 0x4AA930, 0x4AAAB8, 0x4AAEA8),
    "vv5": (0x46F680, 0x403660, 0x4B8450, 0x4B85D8, 0x4B89C8),
}
# VV1/VV2: the villager array's record stride, the record's sex, family and
# first-name number; the name is written to the caller's buffer.
# The Tree of Life and New Believers copy each list with the C runtime's
# sprintf(buffer, list) -- the list is the format, and holds no '%' -- whose
# locale lookup needs the thread's runtime data: the harness copies it.
SPRINTF = {"vv4": 0x4716DB, "vv5": 0x47C046}
RECORD = {"vv1": (0x3D8, 0x350, 0x36C, 0x368), "vv2": (0xE48C, 0x538, 0x554, 0x550)}
FEMALE = {"vv1": 2, "vv2": 2, "vv3": 1, "vv4": 1, "vv5": 1}
ROOM = {"vv1": 0x1C, "vv2": 0x18, "vv3": 0x18, "vv4": 0x18, "vv5": 0x18}

# The owner (2026-10-07): "All newly-spawned villagers from events will
# default to no last name (because otherwise everyone will have the wrong
# last name)".  A mother's delivery and a new village's founders are named
# with a last name; nothing else.  A path is (the naming routine's return
# address, {offset from the routine's entry esp: (a caller's return address,
# the function that call calls)}) -- the stack each creator's call leaves
# (native/vvfp_last_names, WHICH NAMING GETS A LAST NAME;
# native/vvfp_cause_of_death/cod_arrival_sites.inc).
BIRTHS = {
    "vv1": {
        "golden-child mother's extra child": (0x43C692, {0x4C: (0x42EF64, 0x43C350)}),
        "first child": (0x43C692, {0x4C: (0x42EFD5, 0x43C350)}),
        "the Golden Child": (0x43C692, {0x4C: (0x4242FD, 0x43C350)}),
        "twin": (0x43CA28, {0x3C: (0x42F026, 0x43C840)}),
        "triplet": (0x43CA28, {0x3C: (0x42F072, 0x43C840)}),
    },
    "vv2": {
        "first child": (0x44CD3B, {0x188: (0x44F602, 0x44C600)}),
        "twin": (0x44D0BA, {0x3C: (0x43BEE4, 0x44CEC0)}),
        "triplet": (0x44D0BA, {0x3C: (0x43BF30, 0x44CEC0)}),
    },
    "vv3": {
        "first child": (0x4565AD, {0x158: (0x45F1C9, 0x456120), 0x198: (0x45FFD2, 0x45F0B0)}),
        "twin or triplet": (0x4567D9, {0x18: (0x45F2AB, 0x4566E0)}),
    },
    "vv4": {
        "first child": (0x45F338, {0x15C: (0x466302, 0x45EF10), 0x19C: (0x467D92, 0x466270)}),
        "twin (the copy's first naming call)": (0x45DAA6, {0x14: (0x466361, 0x45D9B0),
                                                           0x20: (0x4688F3, 0x466310)}),
        "triplet (the copy's second naming call)": (0x45DAE4, {0x14: (0x466361, 0x45D9B0),
                                                               0x20: (0x468996, 0x466310)}),
    },
    "vv5": {
        "first child": (0x46863D, {0x15C: (0x46FB6F, 0x4681F0), 0x1A4: (0x471EA2, 0x46FAD0)}),
        "twin or triplet": (0x4688F9, {0x18: (0x46FDCE, 0x4687F0)}),
        "twin or triplet (second call)": (0x468937, {0x18: (0x46FDCE, 0x4687F0)}),
    },
}
FOUNDERS = {
    "vv1": {
        "a new tribe, first seeding call": (0x43C692, {0x4C: (0x41C50E, 0x43C350), 0x98: (0x414020, 0x41C000)}),
        "the first tribe's naming, last seeding call": (0x43C692, {0x4C: (0x41C648, 0x43C350),
                                                                   0x98: (0x415491, 0x41C000)}),
        "Start Over": (0x43C692, {0x4C: (0x41C5B6, 0x43C350), 0x98: (0x41C7E5, 0x41C000)}),
    },
    "vv2": {
        "a new tribe": (0x44CD3B, {0x188: (0x4252F7, 0x44C600), 0x1D8: (0x4150B0, 0x424C80)}),
        "the first tribe's naming": (0x44CD3B, {0x188: (0x42545D, 0x44C600), 0x1D8: (0x41AC11, 0x424C80)}),
        "Start Over": (0x44CD3B, {0x188: (0x425413, 0x44C600), 0x1D8: (0x425605, 0x424C80)}),
    },
    "vv3": {
        "a new tribe": (0x4565AD, {0x158: (0x45F1C9, 0x456120), 0x198: (0x428134, 0x45F0B0),
                                   0x1E0: (0x41B7E4, 0x427F70)}),
        "the first tribe's naming": (0x4565AD, {0x158: (0x45F1C9, 0x456120), 0x198: (0x4282E6, 0x45F0B0),
                                                0x1E0: (0x41BA0F, 0x427F70)}),
        "Start Over": (0x4565AD, {0x158: (0x45F1C9, 0x456120), 0x198: (0x428215, 0x45F0B0),
                                  0x1E0: (0x4283F2, 0x427F70)}),
    },
    "vv4": {
        "the adoption scene's founders": (0x45F338, {0x15C: (0x466302, 0x45EF10), 0x19C: (0x43B929, 0x466270)}),
        "the founders' balancing": (0x45F338, {0x15C: (0x466302, 0x45EF10), 0x19C: (0x420268, 0x466270)}),
    },
    "vv5": {
        "the choose-your-founders screen": (0x46863D, {0x15C: (0x46FB6F, 0x4681F0), 0x1A4: (0x43E317, 0x46FAD0)}),
        "the seeding's balancing": (0x46863D, {0x15C: (0x46FB6F, 0x4681F0), 0x1A4: (0x425D48, 0x46FAD0)}),
    },
}
NO_LAST_NAME = {
    "vv1": {
        "Barrel of Babies": (0x43C692, {0x4C: (0x428268, 0x43C350)}),
        "A Mysterious Crate": (0x43C692, {0x4C: (0x42C3F4, 0x43C350)}),
        "The Mysterious Face": (0x43C692, {0x4C: (0x41974F, 0x43C350)}),
        "the startup scan's seeding (a load overwrites it)": (0x43C692, {0x4C: (0x41C50E, 0x43C350),
                                                                         0x98: (0x41D26D, 0x41C000)}),
        "a delivery's return in the twin path's slot": (0x43C692, {0x3C: (0x42F026, 0x43C840)}),
    },
    "vv2": {
        "the event wrapper (Barrel of Babies, Old Friends, ...)": (0x44CD3B, {0x188: (0x44F5B0, 0x44C600)}),
        "the startup scan's seeding": (0x44CD3B, {0x188: (0x4252F7, 0x44C600), 0x1D8: (0x42641D, 0x424C80)}),
        "The Silver Mirror": (0x44D0BA, {0x3C: (0x4217FE, 0x44CEC0)}),
    },
    "vv3": {
        "the canoe and the barrels": (0x4565AD, {0x158: (0x45F1C9, 0x456120), 0x198: (0x45FF80, 0x45F0B0)}),
        "the startup scan's seeding": (0x4565AD, {0x158: (0x45F1C9, 0x456120), 0x198: (0x428134, 0x45F0B0),
                                                  0x1E0: (0x4285EA, 0x427F70)}),
        "The Crystal of Reflections": (0x4567D9, {0x18: (0x45F3A8, 0x4566E0)}),
    },
    "vv4": {
        "the canoe and the barrels": (0x45F338, {0x15C: (0x466302, 0x45EF10), 0x19C: (0x467D40, 0x466270)}),
        "a ghost": (0x45F338, {0x15C: (0x4663E5, 0x45EF10)}),
    },
    "vv5": {
        "Barrel O' Babies and the other events": (0x46863D, {0x15C: (0x46FB6F, 0x4681F0),
                                                             0x1A4: (0x471E50, 0x46FAD0)}),
        "a Heathen": (0x46863D, {0x15C: (0x46FC28, 0x4681F0)}),
        "Reanimate's stand-in": (0x46863D, {0x15C: (0x46FE5C, 0x4681F0)}),
    },
}


def stack(path: tuple[int, dict[int, tuple[int, int]]]) -> tuple[int, dict[int, int]]:
    back, slots = path
    return back, {offset: value for offset, (value, _) in slots.items()}


def a_birth(game: str) -> tuple[int, dict[int, int]]:
    return stack(BIRTHS[game]["first child"])

STUBS = 0x7E000000        # the harness's Windows functions
HEAP = 0x7D000000         # VirtualAlloc
DATA = 0x60000000         # villagers and buffers
STACK = 0x70000000
RETURN = 0x7F000000
STOCK_ABSENT = "stock executables are not in the release source archive"
STOCK_PRESENT = STOCK.is_dir()

# stdcall argument bytes of the Windows calls VvfpStartup makes.
ARGS = {b"VirtualQuery": 12, b"VirtualAlloc": 16, b"VirtualProtect": 16, b"VirtualFree": 12,
        b"FlushInstructionCache": 12, b"GetCurrentProcess": 0}


def names(image: bytes, va: int) -> list[str]:
    at = va - 0x400000
    return [n.decode("ascii") for n in image[at:image.index(b"\0", at)].split(b",") if n]


class Game:
    """One stock executable and the shipped companion in an emulator."""

    def __init__(self, game: str, image: bytes | None = None):
        self.game = game
        exe = pefile.PE(str(STOCK / EXE[game]))
        self.image = bytearray(image if image is not None else exe.get_memory_mapped_image())
        routine, rand, *_ = SITES[game]
        self.rand_va = rand
        mu = Uc(UC_ARCH_X86, UC_MODE_32)
        mu.mem_map(0x400000, (len(self.image) + 0xFFF) & ~0xFFF)
        mu.mem_write(0x400000, bytes(self.image))
        mu.mem_write(rand, b"\xC3")               # the game's rand(): the harness answers
        self.sprintf_va = SPRINTF.get(game)
        if self.sprintf_va:
            mu.mem_write(self.sprintf_va, b"\xC3")
        dll = pefile.PE(str(DLL))
        base = dll.OPTIONAL_HEADER.ImageBase
        mu.mem_map(base, (dll.OPTIONAL_HEADER.SizeOfImage + 0xFFF) & ~0xFFF)
        mu.mem_write(base, dll.get_memory_mapped_image())
        mu.mem_map(STUBS, 0x10000)
        self.stubs: dict[int, bytes] = {}
        for entry in dll.DIRECTORY_ENTRY_IMPORT:
            for index, imp in enumerate(entry.imports):
                stub = STUBS + 0x10 * len(self.stubs)
                self.stubs[stub] = imp.name
                n = ARGS.get(imp.name)
                mu.mem_write(stub, b"\xCC" if n is None else (b"\xC2" + struct.pack("<H", n)))
                mu.mem_write(imp.address, struct.pack("<I", stub))
        self.exports = {e.name.decode(): base + e.address for e in dll.DIRECTORY_ENTRY_EXPORT.symbols if e.name}
        mu.mem_map(HEAP, 0x10000)
        self.heap = HEAP
        mu.mem_map(DATA, 0x400000)
        mu.mem_map(STACK - 0x40000, 0x80000)
        mu.mem_map(RETURN, 0x1000)
        mu.mem_write(RETURN, b"\xC3")
        self.mu = mu
        self.rolls: list[int] = []
        self.bounds: list[int] = []
        self.called: list[bytes] = []
        mu.hook_add(UC_HOOK_CODE, self._hook)

    def _hook(self, mu, address, size, user_data):
        esp = mu.reg_read(UC_X86_REG_ESP)
        arg = lambda i: struct.unpack("<I", mu.mem_read(esp + 4 + 4 * i, 4))[0]  # noqa: E731
        if address == self.rand_va:
            bound = arg(0)
            value = self.rolls.pop(0)
            assert 0 <= value < bound, (value, bound)
            self.bounds.append(bound)
            mu.reg_write(UC_X86_REG_EAX, value)
        elif address == self.sprintf_va:
            source = bytes(mu.mem_read(arg(1), 0x800))
            source = source[:source.index(b"\0")]
            assert b"%" not in source
            mu.mem_write(arg(0), source + b"\0")
            mu.reg_write(UC_X86_REG_EAX, len(source))
        elif address in self.stubs:
            name = self.stubs[address]
            self.called.append(name)
            if name == b"VirtualQuery":
                at, info = arg(0), arg(1)
                region = next(r for r in mu.mem_regions() if r[0] <= at <= r[1])
                mu.mem_write(info, struct.pack("<7I", region[0], region[0], 0x40, region[1] + 1 - region[0],
                                               0x1000, 0x20, 0x1000000))
                mu.reg_write(UC_X86_REG_EAX, 28)
            elif name == b"VirtualAlloc":
                mu.reg_write(UC_X86_REG_EAX, self.heap)
                self.heap += 0x1000
            elif name == b"VirtualProtect":
                mu.mem_write(arg(3), struct.pack("<I", 0x20))
                mu.reg_write(UC_X86_REG_EAX, 1)
            elif name in (b"FlushInstructionCache", b"VirtualFree"):
                mu.reg_write(UC_X86_REG_EAX, 1)
            elif name == b"GetCurrentProcess":
                mu.reg_write(UC_X86_REG_EAX, 0xFFFFFFFF)
            else:
                raise AssertionError(f"VvfpStartup called {name!r}")

    def call(self, va: int, args: list[int], ecx: int = 0, callee_pops: int | None = None,
             frame: tuple[int, dict[int, int]] | None = None) -> dict:
        """frame: (return address, {offset from the entry esp: value}) -- the
        callers' return addresses as a creator's call would leave them."""
        mu = self.mu
        esp = STACK - 0x1000
        back = RETURN
        mu.mem_write(esp, b"\0" * 0x400)
        if frame is not None:
            back, slots = frame
            for offset, value in slots.items():
                mu.mem_write(esp + offset, struct.pack("<I", value))
        mu.mem_write(esp, struct.pack(f"<{1 + len(args)}I", back, *args))
        mu.reg_write(UC_X86_REG_ESP, esp)
        mu.reg_write(UC_X86_REG_ECX, ecx)
        kept = {UC_X86_REG_EBX: 0x11111111, UC_X86_REG_ESI: 0x22222222,
                UC_X86_REG_EDI: 0x33333333, UC_X86_REG_EBP: 0x44444444}
        for reg, value in kept.items():
            mu.reg_write(reg, value)
        mu.emu_start(va, back, count=2_000_000)
        pops = 4 * len(args) if callee_pops is None else callee_pops
        return {"esp_ok": mu.reg_read(UC_X86_REG_ESP) == esp + 4 + pops,
                "kept": all(mu.reg_read(reg) == value for reg, value in kept.items())}

    def startup(self) -> None:
        self.call(self.exports["VvfpStartup"], [GAME_NO[self.game], 0])

    def name(self, sex_female: bool, family: int, first_roll: int, family_roll: int | None = None,
             frame: tuple[int, dict[int, int]] | None = None) -> tuple[str, dict]:
        """The game's own routine names a new villager; returns the name.
        frame: the stack a creator's call leaves (BIRTHS, FOUNDERS, NO_LAST_NAME); none
        is a call from nowhere the game makes one."""
        routine = SITES[self.game][0]
        sex = FEMALE[self.game] if sex_female else (1 if self.game in ("vv1", "vv2") else 0)
        self.bounds.clear()
        if self.game in RECORD:
            stride, sex_at, family_at, number_at = RECORD[self.game]
            index = 3
            record = DATA + index * stride
            self.mu.mem_write(record + sex_at, struct.pack("<i", sex))
            self.mu.mem_write(record + family_at, struct.pack("<i", family))
            self.mu.mem_write(record + number_at, struct.pack("<i", first_roll + 1))
            out = DATA + 0x300000
            self.mu.mem_write(out, b"\xEE" * 28)
            state = self.call(routine, [index, out], ecx=DATA, frame=frame)
            text = bytes(self.mu.mem_read(out, 28))
        else:
            villager = DATA + 0x1000
            self.mu.mem_write(villager, b"\0" * 0x40)
            self.mu.mem_write(villager + 4, struct.pack("<i", sex))
            self.rolls = [first_roll] + ([family_roll] if family == -1 else [])
            state = self.call(routine, [family & 0xFFFFFFFF], ecx=villager, frame=frame)
            text = bytes(self.mu.mem_read(villager + 0x10, ROOM[self.game]))
        return text[:text.index(b"\0")].decode("ascii"), state


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
class NewVillagersGetTheirFamilysLastName(unittest.TestCase):
    def lists(self, game):
        image = pefile.PE(str(STOCK / EXE[game])).get_memory_mapped_image()
        _, _, last, male, female = SITES[game]
        return names(image, last), names(image, male), names(image, female)

    def test_the_stock_game_never_reads_its_last_names(self):
        for game in EXE:
            with self.subTest(game=game):
                last, male, _ = self.lists(game)
                name, state = Game(game).name(sex_female=False, family=7, first_roll=4)
                self.assertEqual(name, male[5])
                self.assertTrue(state["esp_ok"] and state["kept"])

    def test_every_family_gives_its_own_last_name(self):
        for game in EXE:
            last, male, female = self.lists(game)
            self.assertEqual(len(last), 50)
            g = Game(game)
            g.startup()
            for family in range(1, 51):
                with self.subTest(game=game, family=family):
                    female_villager = family % 2 == 0
                    name, state = g.name(sex_female=female_villager, family=family, first_roll=family,
                                         frame=a_birth(game))
                    first = (female if female_villager else male)[family + 1]
                    self.assertEqual(name, f"{first} {last[family - 1]}")
                    self.assertTrue(state["esp_ok"], "the routine's own ret is kept")
                    self.assertTrue(state["kept"], "ebx, esi, edi and ebp are the caller's")

    def test_a_family_the_game_rolls_itself_is_the_one_named(self):
        for game in ("vv3", "vv4", "vv5"):
            with self.subTest(game=game):
                last, male, _ = self.lists(game)
                g = Game(game)
                g.startup()
                name, _ = g.name(sex_female=False, family=-1, first_roll=0, family_roll=41, frame=a_birth(game))
                self.assertEqual(g.bounds[-1], 50)
                self.assertEqual(name, f"{male[1]} {last[41]}")    # family = roll + 1 = 42

    def test_a_family_outside_1_to_50_gets_no_last_name(self):
        # A New Home's Golden Child is created with family 199 (0xC7).
        for game, family in (("vv1", 0xC7), ("vv1", 0), ("vv2", 51), ("vv2", -5)):
            with self.subTest(game=game, family=family):
                last, male, _ = self.lists(game)
                g = Game(game)
                g.startup()
                name, state = g.name(sex_female=False, family=family, first_roll=2, frame=a_birth(game))
                self.assertEqual(name, male[3])
                self.assertTrue(state["esp_ok"] and state["kept"])

    def test_every_birth_and_founder_path_gives_the_last_name(self):
        for game in EXE:
            last, male, _ = self.lists(game)
            g = Game(game)
            g.startup()
            for what, path in [*BIRTHS[game].items(), *FOUNDERS[game].items()]:
                with self.subTest(game=game, named=what):
                    name, state = g.name(sex_female=False, family=9, first_roll=3, frame=stack(path))
                    self.assertEqual(name, f"{male[4]} {last[8]}")
                    self.assertTrue(state["esp_ok"] and state["kept"])

    def test_a_villager_an_event_brings_gets_no_last_name(self):
        # The owner (2026-10-07): "All newly-spawned villagers from events
        # will default to no last name (because otherwise everyone will have
        # the wrong last name)" -- events, and the records the game makes and
        # takes away again.
        for game in EXE:
            last, male, _ = self.lists(game)
            g = Game(game)
            g.startup()
            for what, path in [*NO_LAST_NAME[game].items(), ("a call from nowhere", None)]:
                with self.subTest(game=game, creation=what):
                    frame = stack(path) if path is not None else None
                    name, state = g.name(sex_female=False, family=9, first_roll=3, frame=frame)
                    self.assertEqual(name, male[4])
                    self.assertTrue(state["esp_ok"] and state["kept"])

    def test_each_path_is_the_stock_games_own_calls(self):
        # Every `from` follows the creator's call to the naming routine, and
        # every caller's return address follows a call to the function named.
        for game in EXE:
            image = pefile.PE(str(STOCK / EXE[game])).get_memory_mapped_image()

            def target(back: int) -> int | None:
                at = back - 5 - 0x400000
                if image[at] != 0xE8:
                    return None
                return (back + struct.unpack_from("<i", image, at + 1)[0]) & 0xFFFFFFFF

            for what, (back, slots) in [*BIRTHS[game].items(), *FOUNDERS[game].items(), *NO_LAST_NAME[game].items()]:
                with self.subTest(game=game, path=what):
                    self.assertEqual(target(back), SITES[game][0])
                    for value, callee in slots.values():
                        self.assertEqual(target(value), callee, hex(value))

    def test_every_pairing_fits_the_games_name_field(self):
        for game in EXE:
            last, male, female = self.lists(game)
            longest = max(len(f) for f in male + female) + 1 + max(len(n) for n in last)
            with self.subTest(game=game):
                self.assertLess(longest + 1, ROOM[game])

    def test_only_the_stock_routine_is_detoured(self):
        for game in EXE:
            routine = SITES[game][0]
            with self.subTest(game=game):
                g = Game(game)
                before = bytes(g.mu.mem_read(routine, 6))
                g.startup()
                after = bytes(g.mu.mem_read(routine, 6))
                self.assertEqual(before[:2], b"\x81\xEC")
                self.assertEqual(after[0], 0xE9)
                self.assertEqual(after[5], 0x90)
                self.assertEqual(set(g.called) - set(ARGS), set())
                # a second VvfpStartup changes nothing more
                g.startup()
                self.assertEqual(bytes(g.mu.mem_read(routine, 6)), after)

    def test_a_different_build_is_left_alone(self):
        for game in EXE:
            routine, _, last_list, *_ = SITES[game]
            for what in ("prologue", "list", "a creator's call"):
                with self.subTest(game=game, changed=what):
                    image = bytearray(pefile.PE(str(STOCK / EXE[game])).get_memory_mapped_image())
                    if what == "prologue":
                        image[routine - 0x400000 + 2] ^= 0x10
                    elif what == "a creator's call":
                        back = list(BIRTHS[game].values())[-1][0]
                        image[back - 4 - 0x400000] ^= 0x01     # the call now lands elsewhere
                    else:
                        at = last_list - 0x400000
                        image[image.index(b",", at)] = ord(";")   # 49 names
                    g = Game(game, image)
                    g.startup()
                    self.assertEqual(bytes(g.mu.mem_read(routine, 6)), bytes(image[routine - 0x400000:][:6]))
                    self.assertNotIn(b"VirtualProtect", g.called)


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
class TheRows(unittest.TestCase):
    def test_each_game_ships_the_companion_and_patches_no_byte(self):
        import vv_fun_patcher as vfp
        from vv_fun_patcher_gui import default_fun_patch_selection
        sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
        catalog = {p.id: p for p in vfp.load_fun_patches()}
        for game in EXE:
            with self.subTest(game=game):
                row = catalog[f"{game}_last_names"]
                self.assertEqual(row.raw["patches"], [])
                self.assertEqual(row.raw["companion_files"],
                                 [{"source": "assets/last_names/VVFP Last Names.dll",
                                   "destination": "VVFP Last Names.dll", "sha256": sha}])
                detour = row.raw["runtime_detours"][0]
                self.assertEqual(int(detour["va"], 16), SITES[game][0])
                self.assertTrue(default_fun_patch_selection(row.id))
                self.assertNotIn("dependencies", row.raw)

    def test_the_startup_loader_starts_it(self):
        import vv_fun_patcher as vfp
        bit = 1 << (vfp.STARTUP_LOADER_COMPANIONS.index("VVFP Last Names.dll") + 1)
        for game in EXE:
            with self.subTest(game=game):
                build = next(b for b in vfp.load_builds() if b.id == game)
                features = vfp._attach_automatic_companions(
                    game, vfp._selected_fun_patches(build, [f"{game}_last_names"]))
                self.assertEqual(vfp._startup_loader_mask(game, features), bit)
                for mode in ("stock", "collection_progression", "immediate_fixed"):
                    data, _ = vfp.render_patched_bytes(STOCK / build.input_name, build, mode,
                                                       [f"{game}_last_names"])
                    bare, _ = vfp.render_patched_bytes(STOCK / build.input_name, build, mode, [])
                    self.assertEqual(bytes(data), bytes(bare),
                                     "the row itself changes no byte; the loader is added at publication")

    def test_the_generator_reproduces_the_rows(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import build_last_names_features as gen
        sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
        for game in EXE:
            with self.subTest(game=game):
                on_disk = json.loads((ROOT / "data" / f"{game}_last_names_feature.json").read_text(encoding="utf-8"))
                self.assertEqual(on_disk, gen.row(game, sha))


if __name__ == "__main__":
    unittest.main()
