"""The Secret City (VV3): run the stock game's own farming code in unicorn, frame by frame and in catch-up.

Used by tests/test_game_mechanics_farmers_vv3.py, which pins src/vv_game_mechanics_farmers_vv3.py.

What runs is the stock executable's code, unchanged:
  * the program's static constructors (the table 0x4A400C..0x4A411C: every game object's vtables, the action table
    0x596970 (0x453D20), the item-listener registry 0x58EDB8, the trees 0x5947E0, the hive 0x5945D0, the trigger
    table 0x560958, the villager manager 0x59E110 ...);
  * the map loader 0x4201F0 over the game's own cmap.dat (the 256 x 256 walk grid and every area's points), and
    wpts.dat read into 0x560964 as the game's start-up 0x4279C2 reads it;
  * live play: a villager's per-frame update 0x456E90 (called by the manager 0x45F3B0 once a frame while the speed
    value game+0x12F20 is below 999): the step runner 0x45C440 (a step ends when the clock 0x403330 passes its end
    second, 0x460EA0), the step starters 0x461BF0 / per-frame steps 0x461FB0, the walk 0x458760 (re-aimed every 10
    frames by 0x459490, speed set by 0x455A00 / 0x457290), the map's trigger cells 0x420610 -> 0x422C70, and on an
    empty queue the once-a-second scheduler 0x45BFE0 -> the job chooser 0x459730 -> the work dispatcher 0x45AF00 /
    the remembered-site continuation 0x45AA90;
  * the farming jobs: fruit 0x44BF00 (action 0x7D), honey 0x446E40 (0x6B), fishing 0x453440 (0xB), and what pays
    them: the trees' pick 0x4348F0 -> award 0x434A80, the hive's release listener 0x431A40, the fish step 0x458DB0,
    all through the food writer 0x4263F0;
  * catch-up: the job turn 0x45BF00 (the instant runner 0x45B790) with the catch-up flag game+0x12FB4 set, and the
    aging loop 0x45FFE0 (the meal, the job turns).

Replaced (each named where a test relies on it):
  * rand(N) 0x4032D0: a seeded uniform random number, or a value forced for one call site;
  * the step clock 0x403330 (whole real-life seconds, time() minus the epoch 0x4A4210): the emulated real time;
  * the game object 0x428B60 (a 0x12FD4-byte object the real game allocates): a zeroed block holding the speed
    value (+0x12F20), the difficulty (+0x12F08) and the catch-up flag (+0x12FB4);
  * the text table 0x42F740 / 0x42F190 (strings only), the settings object 0x402C90 (the data path) and fopen
    0x46F47B (no file: the data is put in place first), atexit 0x46FE9A and operator new 0x46EC93 (a bump heap).
"""
from __future__ import annotations

import random
import struct
from pathlib import Path

import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EIP, UC_X86_REG_ESP, UC_X86_REG_FPCW

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Secret City.exe"
DATA = ROOT / "research" / "game-data" / "vv3"
CMAP, WPTS = DATA / "cmap.dat", DATA / "wpts.dat"

FRAME_MS = 33              # 1000 // 30: the frame limiter 0x409A88..0x409AB2 (fps 30 from the settings 0x403380)
REC = 0x1F8C               # a villager record
GAME_FPCW = 0x027F         # the C runtime's 53-bit precision (see tests/test_vv3_fruit_harvested_at_food_bin.py)

# The game's routines.
RAND, CLOCK, GAME_OBJECT = 0x4032D0, 0x403330, 0x428B60
TEXT_TABLE, TEXT, SETTINGS, FOPEN, ATEXIT, NEW = 0x42F740, 0x42F190, 0x402C90, 0x46F47B, 0x46FE9A, 0x46EC93
LOAD_MAP, UPDATE, RUNNER, SET_JOB = 0x4201F0, 0x456E90, 0x45C440, 0x455570
SCHEDULER, CHOOSER, DISPATCH, CONTINUE = 0x45BFE0, 0x459730, 0x45AF00, 0x45AA90
CATCH_UP_TURN, AGING = 0x45BF00, 0x45FFE0
FOOD_ADD = 0x4263F0
FRUIT_JOB, HONEY_JOB, FISH_JOB = 0x7D, 0x6B, 0xB  # actions (handlers 0x44BF00, 0x446E40, 0x453440)
INITIALIZERS = (0x4A400C, 0x4A4120)             # the static constructors run (0x4A4004 / 0x4A4008 are the CRT's own)
SKIPPED_INITIALIZERS = (0x47B0C0, 0x47B0E0)     # the two picture/sound tables 0x595820 / 0x595874 (they need a
#                                                 loaded resource file; nothing in farming reads them)

# Globals.
MAP, WAYPOINTS = 0x4B8700, 0x560964
FOOD, FOOD_GATHERED = 0x582490, 0x5824AC
SPEED_COPY = 0x5825F4                            # what the fruit and honey yields divide by (0x426580)
TECH = 0x582618                                  # technology levels (0x426FC0); +4 Leadership
TREES, HIVE, PUZZLES, MESSAGES = 0x5947E0, 0x5945D0, 0x594990, 0x594C40
MANAGER = 0x59E110
HONEY = HIVE + 0x10                              # the hive's honey (0 to 3,000)
HIVE_ACTIVE = HIVE + 0x14                        # the hive's saved flag its take listener 0x431D79 requires

# Game object offsets.
SPEED, DIFFICULTY, CATCHING_UP = 0x12F20, 0x12F08, 0x12FB4

# Villager record offsets.
QUEUE_TYPE = 0x0
AGE, PROCESSED = 0xDC4, 0xE74                    # the age shown, and the age units already counted
HEALTH, CHIEF, SICK, NURSING = 0xE78, 0xE80, 0xE89, 0xE8C
SITE = 0xEA0                                     # the remembered work site (0x17-0x19 a tree, 0x15 the hive, 0x1C the sea)
SKILLS = {"farming": 0xEAC, "breeding": 0xEB0, "healing": 0xEB4, "research": 0xEB8, "building": 0xEBC}
PREFERENCE = 0xEC0                               # -1 none, 0 Farming
X, Y = 0xEE0, 0xEE4
ACTIVE, ITEM, JOB = 0xF10, 0xF20, 0xF24
LIKES, DISLIKES = 0xFB4, 0xFC0
GAME_PTR, TEXT_PTR = 0x1F78, 0x1F80

STACK, HEAP, GAME, RET, FAKE, PARAMS = 0x30000000, 0x31000000, 0x32000000, 0x33000000, 0x34000000, 0x35000000


class Village:
    """The stock exe in an emulator: the game's objects built by its own constructors, the real map, and one
    villager (manager slot 0) of a grown village (3 fruit trees, the hive, every puzzle solved)."""

    _base_memory: dict | None = None

    def __init__(self, *, seed: int = 1, speed: int = 6, food: int = 1000, fruit: int = 1000, honey: int = 3000,
                 difficulty: int = 1, leadership: int = 0):
        pe = pefile.PE(str(STOCK), fast_load=True)
        base = pe.OPTIONAL_HEADER.ImageBase
        size = (pe.OPTIONAL_HEADER.SizeOfImage + 0xFFF) & ~0xFFF
        uc = Uc(UC_ARCH_X86, UC_MODE_32)
        uc.mem_map(base, size)
        self.uc, self.image_base, self.image_size = uc, base, size
        for area, length in ((STACK, 0x100000), (HEAP, 0x1000000), (GAME, 0x20000), (RET, 0x1000), (FAKE, 0x10000),
                             (PARAMS, 0x1000)):
            uc.mem_map(area, length)
        uc.reg_write(UC_X86_REG_FPCW, GAME_FPCW)
        self.rng = random.Random(seed)
        self.by_caller: dict[int, int] = {}      # a rand(N) call's return address -> the value it gets
        self.t = 100_000.0                        # emulated real time, seconds
        self.frame = 0
        self.heap = HEAP + 0x1000
        self.credits: list[tuple[int, int, int]] = []   # (frame, amount, the food writer's caller) per 0x4263F0
        stubs = {RAND: self._rand, CLOCK: lambda: self._ret(int(self.t), 0), GAME_OBJECT: lambda: self._ret(GAME, 0),
                 TEXT_TABLE: lambda: self._ret(FAKE, 0), TEXT: lambda: self._ret(FAKE + 0x300, 4),
                 SETTINGS: lambda: self._ret(FAKE, 0), FAKE + 0x200: lambda: self._ret(FAKE + 0x300, 4),
                 FOPEN: lambda: self._ret(0, 0), ATEXIT: lambda: self._ret(0, 0), NEW: self._new}
        for address, stub in stubs.items():
            uc.hook_add(UC_HOOK_CODE, lambda _u, _a, _s, _d, stub=stub: stub(), begin=address, end=address)
        uc.hook_add(UC_HOOK_CODE, self._on_food, begin=FOOD_ADD, end=FOOD_ADD)
        if Village._base_memory is None:
            self._build(pe)
            Village._base_memory = {"image": bytes(uc.mem_read(base, size)), "heap": bytes(uc.mem_read(HEAP, 0x100000)),
                                    "fake": bytes(uc.mem_read(FAKE, 0x10000)), "next": self.heap}
        else:
            mem = Village._base_memory
            uc.mem_write(base, mem["image"])
            uc.mem_write(HEAP, mem["heap"])
            uc.mem_write(FAKE, mem["fake"])
            self.heap = mem["next"]
        self.w32(GAME + SPEED, speed)
        self.w32(SPEED_COPY, speed)
        self.w32(GAME + DIFFICULTY, difficulty)
        self.w32(TECH + 4 * 4, leadership)
        self.w32(FOOD, food)
        self.w32(HONEY, honey)
        for tree in range(3):
            self.w32(TREES + 0x30 + tree * 0x18, fruit)
        self.rng = random.Random(seed)                # the same draws whether or not this emulator built the objects

    def _build(self, pe) -> None:
        uc = self.uc
        uc.mem_write(self.image_base, pe.header)
        for section in pe.sections:
            data = section.get_data()
            room = self.image_size - section.VirtualAddress
            uc.mem_write(self.image_base + section.VirtualAddress, data[: max(0, min(len(data), room))])
        self.w32(FAKE, FAKE + 0x100)                 # the settings object: vtable slot 2 gives the data path
        self.w32(FAKE + 0x108, FAKE + 0x200)
        uc.mem_write(FAKE + 0x300, b"x\0")
        self._load_map()                             # the huts' constructor reads the map
        first, last = INITIALIZERS
        for at in range(first, last, 4):
            thunk = self.r32(at) & 0xFFFFFFFF
            if thunk and thunk not in SKIPPED_INITIALIZERS:
                self.call(thunk, count=20_000_000)
        self._load_map()                             # the map's own constructor (0x4201C0) cleared it
        uc.mem_write(WAYPOINTS, WPTS.read_bytes())
        # A grown village: 3 trees planted (kinds 0, 1, 2), the hive active, every puzzle solved, every tutorial
        # message already shown (so the skill test 0x45A2C0 has no first-failure grace, 0x45A354..0x45A38B).
        self.w32(TREES + 0x64, 3)
        for tree in range(3):
            self.w32(TREES + 0x2C + tree * 0x18, tree)
        uc.mem_write(HIVE_ACTIVE, b"\x01")
        for puzzle in range(16):
            self.w32(PUZZLES + puzzle * 8, self.r32(0x49D230 + puzzle * 4))
        for message in range(0xB80 // 32):            # message 0x279 + k's flag: byte 32 x k (0x436F70)
            uc.mem_write(MESSAGES + 32 * message, b"\x01")

    def _load_map(self) -> None:
        self.uc.mem_write(MAP, CMAP.read_bytes())
        self.call(LOAD_MAP, MAP, count=50_000_000)

    # -- memory -----------------------------------------------------------------------------------------------
    def w32(self, address: int, value: int) -> None:
        self.uc.mem_write(address, struct.pack("<I", value & 0xFFFFFFFF))

    def r32(self, address: int) -> int:
        return struct.unpack("<i", self.uc.mem_read(address, 4))[0]

    def rec(self, index: int = 0) -> int:
        return MANAGER + 0x14 + index * REC

    def food(self) -> int:
        return self.r32(FOOD)

    def fruit(self, tree: int) -> int:
        return self.r32(TREES + 0x30 + tree * 0x18)

    def area_points(self, area: int) -> list[tuple[int, int]]:
        count = self.r32(MAP + 0xA8000 + area * 4)
        start = MAP + ((area + 0x20) << 10) * 8
        return [struct.unpack("<ii", self.uc.mem_read(start + i * 8, 8)) for i in range(count)]

    def region(self, x: int, y: int) -> int:
        return self.call(0x4205B0, MAP, x, y)

    # -- stubs ------------------------------------------------------------------------------------------------
    def _ret(self, value: int, pop: int) -> None:
        sp = self.uc.reg_read(UC_X86_REG_ESP)
        back = struct.unpack("<I", self.uc.mem_read(sp, 4))[0]
        self.uc.reg_write(UC_X86_REG_EAX, value & 0xFFFFFFFF)
        self.uc.reg_write(UC_X86_REG_ESP, sp + 4 + pop)
        self.uc.reg_write(UC_X86_REG_EIP, back)

    def _rand(self) -> None:
        sp = self.uc.reg_read(UC_X86_REG_ESP)
        caller, n = struct.unpack("<Ii", self.uc.mem_read(sp, 8))
        if caller in self.by_caller:
            value = self.by_caller[caller]
        else:
            value = self.rng.randrange(n) if 1 < n <= 0x7FFF else 0
        self._ret(value, 0)

    def _new(self) -> None:
        size = struct.unpack("<I", self.uc.mem_read(self.uc.reg_read(UC_X86_REG_ESP) + 4, 4))[0]
        block = self.heap
        self.heap += (size + 15) & ~15
        self._ret(block, 0)

    def _on_food(self, *_):
        sp = self.uc.reg_read(UC_X86_REG_ESP)
        caller, amount = struct.unpack("<Ii", self.uc.mem_read(sp, 8))
        self.credits.append((self.frame, amount, caller))

    def call(self, function: int, this: int = 0, *args: int, count: int = 5_000_000) -> int:
        sp = STACK + 0x80000
        for value in reversed(args):
            sp -= 4
            self.uc.mem_write(sp, struct.pack("<I", value & 0xFFFFFFFF))
        sp -= 4
        self.uc.mem_write(sp, struct.pack("<I", RET))
        self.uc.reg_write(UC_X86_REG_ESP, sp)
        self.uc.reg_write(UC_X86_REG_ECX, this)
        self.uc.emu_start(function, RET, count=count)
        if self.uc.reg_read(UC_X86_REG_EIP) != RET:
            raise RuntimeError(f"0x{function:X} did not return")
        return self.uc.reg_read(UC_X86_REG_EAX)

    # -- the villager -------------------------------------------------------------------------------------------
    def villager(self, *, feet=(1136, 1264), age: int = 500, health: int = 80, skills: dict | None = None,
                 preference: int = -1, site: int = 0, likes=(), dislikes=(), index: int = 0) -> int:
        """A villager standing at `feet` (what 0x455EF0 returns: the walk aims it); by default at the food bin."""
        record = self.rec(index)
        self.uc.mem_write(record, bytes(REC))
        self.uc.mem_write(record + ACTIVE, b"\x01")
        self.w32(record + HEALTH, health)
        self.w32(record + AGE, age)
        self.w32(record + PROCESSED, age)
        self.w32(record + ITEM, -1)
        self.w32(record + SITE, site)
        self.w32(record + PREFERENCE, preference)
        for k in range(3):
            self.w32(record + LIKES + 4 * k, likes[k] if k < len(likes) else -1)
            self.w32(record + DISLIKES + 4 * k, dislikes[k] if k < len(dislikes) else -1)
        for name, off in SKILLS.items():
            self.w32(record + off, (skills or {}).get(name, 10))
        self.w32(record + GAME_PTR, GAME)
        self.w32(record + TEXT_PTR, FAKE)
        self.place(feet, record)
        return record

    def place(self, feet, record: int | None = None) -> None:
        self.call(0x455EB0, record or self.rec(0), feet[0], feet[1])

    def feet(self, record: int | None = None) -> tuple[int, int]:
        self.call(0x455EF0, record or self.rec(0), PARAMS + 0x100)
        return struct.unpack("<ii", self.uc.mem_read(PARAMS + 0x100, 8))

    def queue_type(self, record: int | None = None) -> int:
        return self.r32(record or self.rec(0))

    # -- live play ------------------------------------------------------------------------------------------------
    def step_frame(self) -> None:
        """One frame of the village screen: the manager's update 0x45F3B0 runs 0x456E90 for each active villager."""
        self.call(UPDATE, self.rec(0), count=5_000_000)
        self.frame += 1
        self.t += FRAME_MS / 1000.0

    def start_job(self, job: int, param: int = 0) -> None:
        """Give villager 0 `job` as the dispatcher does (0x455570 writes the job and runs its handler)."""
        self.w32(PARAMS, param)
        self.call(SET_JOB, self.rec(0), job, PARAMS)

    def run_trip(self, job: int, param: int = 0, max_frames: int = 60_000) -> tuple[int, int]:
        """Start `job` now; frames until its food is credited (-1: none), and until its step queue is empty."""
        start, seen = self.frame, len(self.credits)
        self.start_job(job, param)
        paid = None
        while self.frame - start < max_frames:
            self.step_frame()
            if paid is None and len(self.credits) > seen:
                paid = self.frame - start
            if self.queue_type() == 0:
                return (paid if paid is not None else -1), self.frame - start
        raise RuntimeError("the trip never ended")

    # -- catch-up -------------------------------------------------------------------------------------------------
    def catch_up_turn(self) -> None:
        """One catch-up job turn of villager 0, with the catch-up flag set as the aging loop sets it (0x460549)."""
        self.uc.mem_write(GAME + CATCHING_UP, b"\x01")
        try:
            self.call(CATCH_UP_TURN, self.rec(0), self.rec(0), count=5_000_000)
        finally:
            self.uc.mem_write(GAME + CATCHING_UP, b"\x00")

    def aging_loop(self) -> list[int]:
        """Run the aging loop 0x45FFE0 (every villager's uncounted units, until no one is behind) with each job turn
        0x45BF00 only counted: the record of every call."""
        turns: list[int] = []

        def turn(*_):
            sp = self.uc.reg_read(UC_X86_REG_ESP)
            turns.append(struct.unpack("<I", self.uc.mem_read(sp + 4, 4))[0])
            self._ret(0, 4)

        hook = self.uc.hook_add(UC_HOOK_CODE, turn, begin=CATCH_UP_TURN, end=CATCH_UP_TURN)
        try:
            self.call(AGING, MANAGER, count=50_000_000)
        finally:
            self.uc.hook_del(hook)
        return turns

    # -- the game's own scheduler -----------------------------------------------------------------------------------
    PAY_SITES = {0x434AF1: "fruit picks", 0x431C2F: "honey picks", 0x458EEA: "fishing trips", 0x458FE6: "crabs"}

    def scheduler_cycle(self, source: str, farming: int, hours: float) -> dict[str, int]:
        """Villager 0 (set up by the caller) left to the scheduler for `hours` of real-life time, with food kept at
        1,000, the skill held and only `source` open ("fruit", "honey" or "fish"): the paying trips by pay site."""
        record = self.rec(0)
        seen = len(self.credits)
        fish_puzzle = self.r32(0x49D230 + 10 * 4)
        for frame in range(int(hours * 3600 * 1000 / FRAME_MS)):
            if frame % 300 == 0:
                self.w32(FOOD, 1000)
                self.w32(HONEY, 3000 if source == "honey" else 0)
                for tree in range(3):
                    self.w32(TREES + 0x30 + tree * 0x18, 1000 if source == "fruit" else 0)
                self.w32(PUZZLES + 10 * 8, fish_puzzle if source == "fish" else 0)
                self.w32(record + SKILLS["farming"], farming)
            self.step_frame()
        paid: dict[str, int] = {}
        for _, _, caller in self.credits[seen:]:
            if caller in self.PAY_SITES:
                paid[self.PAY_SITES[caller]] = paid.get(self.PAY_SITES[caller], 0) + 1
        return paid
