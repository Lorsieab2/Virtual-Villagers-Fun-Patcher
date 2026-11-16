"""The emulated game for tests/test_gender_presentation.py: an executable (stock, or as the patcher renders it) with
"VVFP Gender Presentation.dll" installed in tests/story_emulator.py, a village in the game's own record table, the
game's save slot, and the in-memory disk of tests/head_look_emulation.py for the DLL's per-save file."""
from __future__ import annotations

from pathlib import Path

from head_look_emulation import GAMES, Disk
from story_emulator import STACK_TOP, Process

ROOT = Path(__file__).resolve().parents[1]
DLL = ROOT / "assets" / "gender_presentation" / "VVFP Gender Presentation.dll"
DOCS = "C:\\Docs"

# Each game's sex values (male, female) and the fields a special villager is told by (native/shared/sex_change.h).
SEXES = {1: (1, 2), 2: (1, 2), 3: (0, 1), 4: (0, 1), 5: (0, 1)}


def presentation_file(slot: int) -> str:
    return (f"{DOCS}\\LDW\\Game\\Virtual Villagers Fun Patcher\\Save {slot}\\Data\\Gender Presentation\\"
            f"Gender Presentation - Save {slot}.dat").lower()


class Game:
    """One game in the emulator with the DLL started and a village in its own records."""

    def __init__(self, game: int, exe: bytes, *, start: bool = True, slot: int = 1, dll: bool = True):
        self.game = game
        self.g = dict(GAMES[game])
        self.p = Process(exe, DLL if dll else None)
        self.disk = Disk(self.p)
        self.p.tick = 1_000_000
        table = self.g.get("table")
        if table is not None:
            manager_imm, slots_imm, base = table
            if self.p.read(manager_imm - 1, 1) == b"\xB9" and self.p.u32(manager_imm) == 0x800000 \
                    and self.p.u32(slots_imm) == 256:
                self.g.update(records=0x800000 + base, count=256)
        pool = self.g.get("pool_global")
        if pool is not None:
            self.g["records"] = self.p.alloc(self.g["count"] * self.g["stride"])
            self.p.put32(pool, self.g["records"])
        if dll and start:
            self.p.export("VvfpStartup", game, 0)
        manager = self.p.alloc(self.g["slot_field"] + 0x100)
        self.p.put32(self.g["manager"], manager)
        self.p.put32(manager + self.g["slot_field"], slot)

    @property
    def male(self) -> int:
        return SEXES[self.game][0]

    @property
    def female(self) -> int:
        return SEXES[self.game][1]

    def record(self, i: int) -> int:
        return self.g["records"] + i * self.g["stride"]

    def villager(self, i: int, name: str, *, female: bool = False, age: int = 600, head: int = 4) -> int:
        r = self.record(i)
        self.p.write(r + self.g["present"], b"\x01")
        self.p.write(r + self.g["name"], name.encode() + b"\0")
        self.p.put32(r + self.g["sex"], self.female if female else self.male)
        self.p.put32(r + self.g["age"], age)
        self.p.put32(r + self.g["head"], head)
        return r

    def later(self) -> None:
        self.p.tick += 1000

    def get(self, i: int) -> int:
        self.later()
        return self.p.export("VvfpGenderPresentationGet", self.game, self.record(i))

    def set(self, i: int, on: int) -> int:
        self.later()
        return self.p.export("VvfpGenderPresentationSet", self.game, self.record(i), on)

    def run(self, start: int, *, regs: dict[str, int], until: int, flags: int = 0x202) -> None:
        p = self.p
        p.set_reg("esp", STACK_TOP - 0x4000)
        for name, value in regs.items():
            p.set_reg(name, value)
        p.set_reg("eflags", flags)
        self.later()
        p.mu.emu_start(start, until, count=5_000_000)
