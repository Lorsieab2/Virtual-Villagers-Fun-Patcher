"""The Tree of Life (VV4) and New Believers (VV5): run the stock Nursery School lesson in unicorn.

Used by tests/test_game_mechanics_nursery.py, which pins the Nursery School lines of the Game Mechanics page
(src/vv_game_mechanics_catchup.py, vv_game_mechanics_vv4.py, vv_game_mechanics_vv5.py, vv_game_mechanics_items_vv4.py
and vv_game_mechanics_items_vv5.py).

What runs is the stock executable's code, unchanged: the lesson inside the noni / world tick (VV5 0x425F80-0x4260AD,
VV4 0x4203F3-0x420521), with the game's own teacher finder (VV5 0x471BB0, VV4 0x467C50), record lookup (0x46F950 /
0x466040), skill total (0x475670 / 0x46ACD0), highest skill (0x4755C0 / 0x46AC20), skill adder (0x475730 / 0x46AD80)
and float-to-int (0x47C9B0 / 0x471630).  The villager table is the exe's own static one (VV5 0x554148, records at +0x48,
0x2F44 bytes; VV4 0x50E568, records at +0x44, 0x2E3C bytes), zeroed, with only the villagers a test makes.

Replaced: the game's RNG(n) (VV5 0x403660, VV4 0x4036D0, rand() % n): each call takes the next forced value from a
list, so a test chooses every roll (the 50% roll, the teacher pick, the random skill), or (rolls_from) draws it from a
seeded random.Random.  `patched` writes (file offset, stock, fixed) edits into the image first (a .text file offset
is its RVA in both exes), so the same run shows a Fix Vanilla Bugs edit.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_EIP, UC_X86_REG_ESP

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables"


@dataclass(frozen=True)
class Game:
    exe: str
    manager: int        # the villager table
    first: int          # the first record's offset in it
    stride: int
    skills: int         # how many skills
    start: int          # the lesson's first instruction
    end: int            # the first instruction after it
    rand: int
    speed: int          # the speed value's offset in the village manager
    active: int         # the record's active byte
    extra: int          # VV5: the +0x1CE1 byte 0x466170 tests; VV4: the ghost byte +0x1CC7
    health: int         # the teacher finder's health test (VV5 +0x1C40 > 0)
    faction: int | None  # VV5: Heathen +0x1CEC


VV5 = Game("Virtual Villagers - New Believers.exe", 0x554148, 0x48, 0x2F44, 6, 0x425F80, 0x4260AD, 0x403660,
           0x17D7C, 0x1CD4, 0x1CE1, 0x1C40, 0x1CEC)
VV4 = Game("Virtual Villagers - The Tree of Life.exe", 0x50E568, 0x44, 0x2E3C, 5, 0x4203F3, 0x420521, 0x4036D0,
           0x17110, 0x1CC4, 0x1CC7, 0x1C40, None)
AGE, JOB, SKILLS = 0x1B8C, 0x1C54, 0x1C5C
GAME_PTR = 0x00300000          # a stand-in village manager: [GAME_PTR_HOLDER] -> it, speed at its +speed
HOLDER = 0x00340000
STACK_TOP = 0x00200000


def available(game: Game) -> bool:
    return (STOCK / game.exe).is_file()


class Nursery:
    def __init__(self, game: Game, *, speed: int = 6, patched=()) -> None:
        self.g = game
        pe = pefile.PE(str(STOCK / game.exe), fast_load=True)
        image = pe.get_memory_mapped_image()
        self.uc = uc = Uc(UC_ARCH_X86, UC_MODE_32)
        size = (len(image) + 0xFFFF) & ~0xFFFF
        uc.mem_map(0x400000, size)
        uc.mem_write(0x400000, image)
        for offset, before, after in patched:     # (file offset, stock, fixed); file offset == RVA in .text
            assert bytes(image[offset:offset + len(before)]) == before, hex(offset)
            uc.mem_write(0x400000 + offset, after)
        table = game.first + 150 * game.stride
        uc.mem_write(game.manager, b"\0" * table)
        uc.mem_map(0x00100000, 0x00100000)       # the stack
        uc.mem_map(GAME_PTR, 0x00040000)
        uc.mem_map(HOLDER, 0x1000)
        uc.mem_write(HOLDER, struct.pack("<I", GAME_PTR))
        uc.mem_write(GAME_PTR + game.speed, struct.pack("<i", speed))
        self.rolls: list[int] = []
        self.rng = None
        self.asked: list[int] = []
        uc.hook_add(UC_HOOK_CODE, self._rand, begin=game.rand, end=game.rand)

    def _rand(self, uc, _address, _size, _data) -> None:
        esp = uc.reg_read(UC_X86_REG_ESP)
        ret, n = struct.unpack("<II", bytes(uc.mem_read(esp, 8)))
        self.asked.append(n)
        value = self.rolls.pop(0) if self.rolls else (self.rng.randrange(n) if self.rng else 0)
        assert 0 <= value < n, (value, n)
        uc.reg_write(UC_X86_REG_EAX, value)
        uc.reg_write(UC_X86_REG_ESP, esp + 4)          # cdecl: the caller pops the argument
        uc.reg_write(UC_X86_REG_EIP, ret)

    def record(self, index: int) -> int:
        return self.g.manager + self.g.first + index * self.g.stride

    def villager(self, index: int, *, age: int, skills: list[float], job: int = 0, heathen: bool = False,
                 health: int = 80, extra: int = 0) -> int:
        at = self.record(index)
        w = self.uc.mem_write
        w(at + self.g.active, b"\x01")
        w(at + self.g.extra, bytes([extra]))
        w(at + AGE, struct.pack("<i", age))
        w(at + JOB, struct.pack("<i", job))
        w(at + self.g.health, struct.pack("<i", health))
        if self.g.faction is not None:
            w(at + self.g.faction, b"\x01" if heathen else b"\x00")
        w(at + SKILLS, struct.pack(f"<{self.g.skills}f", *skills))
        return at

    def skills(self, index: int) -> list[float]:
        at = self.record(index) + SKILLS
        return list(struct.unpack(f"<{self.g.skills}f", bytes(self.uc.mem_read(at, 4 * self.g.skills))))

    def lesson(self, rolls: list[int]) -> list[int]:
        """Run one tick's lesson with these forced rolls; returns the n of every RNG(n) call it made."""
        self.rolls, self.asked = list(rolls), []
        uc = self.uc
        esp = STACK_TOP - 0x100
        uc.mem_write(esp, b"\0" * 0x100)
        uc.mem_write(esp + 0x18, struct.pack("<I", HOLDER))     # VV4 restores its manager holder from here
        uc.reg_write(UC_X86_REG_ESP, esp)
        uc.reg_write(UC_X86_REG_EBX, HOLDER)                     # VV5: [ebx] is the village manager
        uc.reg_write(UC_X86_REG_EBP, HOLDER)                     # VV4: [ebp] is the village manager
        uc.emu_start(self.g.start, self.g.end, count=2_000_000)
        assert not self.rolls, f"unused rolls {self.rolls}"
        return self.asked

    def rolls_from(self, rng) -> list[int]:
        """One tick with every roll drawn from `rng` as the game asks for it."""
        self.rng = rng
        try:
            return self.lesson([])
        finally:
            self.rng = None
