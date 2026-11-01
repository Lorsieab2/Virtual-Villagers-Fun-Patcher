"""The Lost Children (VV2): run the stock game's own farming code in unicorn, frame by frame and in catch-up.

Used by tests/test_game_mechanics_farmers_vv2.py, which pins src/vv_game_mechanics_farmers_vv2.py.

What runs is the stock executable's code, unchanged:
  * the map builder 0x418660 (the 10-pixel walk grid, 170 x 170 dwords indexed x // 10 * 170 + y // 10, read by 0x4181D0), on a village state;
  * the farming jobs: coconuts 0x456F70, crops 0x4593D0, fishing 0x4507A0 (each queues its steps with 0x449B70
    and starts the first with 0x44FBB0), and the work dispatcher 0x45FBF0 that picks among them;
  * live play: the per-frame villager update 0x464CD0 (the village scene calls it once a frame, 0x42F9FF, unless
    the speed value is 999 or more, i.e. paused): the step timers on the game clock 0x403200, the walk 0x45E880
    with the grid path finder 0x41A700, the step starters 0x44FBB0, the skill step 0x44E170, the payoffs
    0x461B10 and the food writer 0x4262B0, the empty-queue wait and the AI decision 0x461850 -> job chooser
    0x449C60 -> dispatcher 0x45FBF0;
  * catch-up: the job turn 0x43B4D0 -> 0x449C60 -> 0x45FBF0 -> the step simulator 0x464680, and the life loop
    0x43BA70..0x43C0BB.

Replaced (each named in the docstring of the test that relies on it):
  * rand(N) 0x4031A0 (rand() % N): a seeded uniform random number, or a forced value;
  * the game clock 0x403200 (whole real seconds, time() minus the save's base): the emulated real time,
    int(seconds);
  * drawing, sound and text only: the text table 0x441680 (returns an empty string), the effects 0x41EA60 /
    0x41EA30 / 0x41E8A0 (the object at manager + 0xE574E4), the particles 0x4239D0 (manager + 0xE574DC) and the draw-order sort 0x44B0E0 (it only reorders
    the index list at manager + 0xE57090).  None of them touches a villager's step queue, position, timers or the
    food.
"""
from __future__ import annotations

import random
import struct
from pathlib import Path

import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Lost Children.exe"
# A grown village's state (the owner's slot 5 save: every technology at level 3, the dam built, Sustainable
# Fishing solved).  Game data, never committed (research/ is ignored).
GROWN = ROOT / "research" / "game-data" / "vv2" / "grown_village.ldw"

FRAME_MS = 33              # 1000 // 30: the frame limiter 0x409318..0x409342 (fps 30: 0x403250 via 0x40299B, 0x408340)
REC = 0xE48C               # a villager record

# The game's routines.
RAND, CLOCK = 0x4031A0, 0x403200
UPDATE, CATCH_UP_TURN, BUILD_MAP = 0x464CD0, 0x43B4D0, 0x418660
LIFE_LOOP, LIFE_LOOP_END = 0x43BA6C, 0x43C0B5
COCONUTS, CROPS, FISH, WATER = 0x456F70, 0x4593D0, 0x4507A0, 0x45D280
DISPATCH, CHOOSER, AI = 0x45FBF0, 0x449C60, 0x461850
CALLBACK, FOOD_ADD = 0x461B10, 0x4262B0
TEXT = 0x441680                                             # thiscall, 1 argument: a string from the text table
COSMETIC = {0x41EA60: 0x1C, 0x41EA30: 0x18, 0x41E8A0: 4,     # routine -> bytes it pops (ret n)
            0x4239D0: 0x1C,   # a particle (the object at manager + 0xE574DC; e.g. the rest step 0x4499C0, 0x449A71)
            0x44B0E0: 0}   # the draw-order sort of the index list at manager + 0xE57090 (every 11th update)
ITEM_GETTER = 0x416060    # the item (mushroom / collectible) object the map builder's tail reads (0x41A6D3)

# State offsets (a save's file offset is 4 more).
FOOD, COCONUT_COUNT, FISH_COUNT, ALLOWANCE, CROP_COUNT = 0x2EAA4, 0x2EACC, 0x2EAD0, 0x2EAD4, 0x2EAD8
LEVELS, FARMING_LEVEL, DIFFICULTY, SPEED = 0x2EA74, 0x2EA9C, 0x2EAEC, 0x2EB08
DAM, FISHING_SOLVED, CATCHING_UP, TUTORIAL = 0x2E798, 0x2E7E8, 0x3046C, 0x1BF
VILLAGERS_PTR = 0x305A4
STATE_SIZE = 0x40000

# Villager record offsets.
X, Y, QUEUE, TIMER, WAIT = 0x4, 0x8, 0x4C, 0x58, 0x804
ALIVE, HEALTH, AGE, PROC_AGE, SEX, SICK, NURSING, TOTEM = 0x30, 0x52C, 0x530, 0x534, 0x538, 0x53C, 0x540, 0x558
LIKES, DISLIKES = 0x5F0, 0x6E8                 # 62 codes each (0x445510 / 0x4454E0)
ASSIGNED, PREFERENCE = 0x7E0, 0x7F8
SKILLS = {"parenting": 0x7E4, "building": 0x7E8, "farming": 0x7EC, "healing": 0x7F0, "research": 0x7F4}

STACK, STATE, MAP, BUF, FX, TXT, ITEM, WORLD, RET = (0x30000000, 0x31100000, 0x31200000, 0x31300000, 0x31400000,
                                                    0x31500000, 0x31600000, 0x31700000, 0x31800000)
MGR = 0x20000000
MGR_SIZE = 0xE58000

_IMAGE: tuple[int, bytes] | None = None


def _image() -> tuple[int, bytes]:
    global _IMAGE
    if _IMAGE is None:
        pe = pefile.PE(str(STOCK), fast_load=True)
        _IMAGE = pe.OPTIONAL_HEADER.ImageBase, pe.get_memory_mapped_image()
    return _IMAGE


def grown_state() -> bytes:
    return GROWN.read_bytes()


class Village:
    """The stock exe in an emulator, with one villager (index 0) and a village state (a save's, or built from
    scratch: every technology at level `levels`)."""

    def __init__(self, *, seed: int = 1, speed: int = 6, state: bytes | None = None, levels: int = 3,
                 dam: bool = True, food: int = 1000, coconuts: int = 1500, fish: int = 0, fishing_solved: bool = True,
                 crops: int = 800, allowance: int = 100_000, difficulty: int = 1, farming_level: int | None = None):
        base, image = _image()
        uc = Uc(UC_ARCH_X86, UC_MODE_32)
        uc.mem_map(base, (len(image) + 0xFFFF) & ~0xFFFF)
        uc.mem_write(base, image)
        for area, size in ((STACK, 0x200000), (MGR, MGR_SIZE), (STATE, STATE_SIZE), (MAP, 0x20000),
                           (BUF, 0x10000), (FX, 0x10000), (TXT, 0x1000), (ITEM, 0x1000), (WORLD, 0x1000),
                           (RET, 0x1000)):
            uc.mem_map(area, size)
        self.uc = uc
        self.rng = random.Random(seed)
        self.forced: list[int] | None = None
        self.by_caller: dict[int, int] = {}         # a rand(N) call's return address -> the value it gets
        self.t = 1000.0                             # emulated real time, seconds since the save's base
        self.frame = 0
        self.rewards: list[tuple[int, int]] = []    # (frame, callback id) for each payoff 0x461B10 call
        self.food_log: list[tuple[int, int]] = []   # (frame, food added) for each 0x4262B0 call
        self.rand_calls = 0
        self.farming_fixed: int | None = None      # hold villager 0's Farming here every frame (no learning)
        if state is not None:                       # a save's state: file offset 0xC on is state + 8 on
            uc.mem_write(STATE + 8, state[0xC:])
        else:                                       # a state from scratch: technologies at `levels`
            for k in range(6):
                self.w32(STATE + LEVELS + 8 * k, levels)
        self.w32(MGR + 0xE574D4, STATE)
        self.w32(MGR + 0xE574D8, MAP)
        self.w32(MGR + 0xE574DC, FX)
        self.w32(MGR + 0xE574E4, FX)
        self.w32(MGR + 0xE574F0, TXT)
        self.w32(STATE + VILLAGERS_PTR, MGR)
        self.w32(MAP + 0x1C394, STATE)
        self.w32(MAP + 0x1C398, BUF)
        self.w32(WORLD, STATE)                      # the world object of the tick: [+0] state, [+4] villagers
        self.w32(WORLD + 4, MGR)
        if farming_level is not None:
            self.w32(STATE + FARMING_LEVEL, farming_level)
        self.w8(STATE + DAM, 1 if dam else 0)
        self.w8(STATE + FISHING_SOLVED, 1 if fishing_solved else 0)
        self.w8(STATE + TUTORIAL, 0)
        self.w8(STATE + CATCHING_UP, 0)
        self.w32(STATE + DIFFICULTY, difficulty)
        self.w32(STATE + FOOD, food)
        self.w32(STATE + COCONUT_COUNT, coconuts)
        self.w32(STATE + FISH_COUNT, fish)
        self.w32(STATE + CROP_COUNT, crops)
        self.w32(STATE + ALLOWANCE, allowance)
        self.w32(STATE + SPEED, speed)
        stubs = {RAND: self._rand, CLOCK: lambda: self._ret(int(self.t), 0), TEXT: lambda: self._ret(BUF, 4),
                 ITEM_GETTER: lambda: self._ret(ITEM, 0)}
        for address, pop in COSMETIC.items():
            stubs[address] = lambda pop=pop: self._ret(0, pop)
        for address, stub in stubs.items():
            uc.hook_add(UC_HOOK_CODE, lambda _u, _a, _s, _d, stub=stub: stub(), begin=address, end=address)
        uc.hook_add(UC_HOOK_CODE, self._on_reward, begin=CALLBACK, end=CALLBACK)
        uc.hook_add(UC_HOOK_CODE, self._on_food, begin=FOOD_ADD, end=FOOD_ADD)
        self.call(BUILD_MAP, MAP, count=20_000_000)

    # -- memory -------------------------------------------------------------------------------------------------
    def w32(self, address: int, value: int) -> None:
        self.uc.mem_write(address, struct.pack("<I", value & 0xFFFFFFFF))

    def w8(self, address: int, value: int) -> None:
        self.uc.mem_write(address, bytes([value & 0xFF]))

    def r32(self, address: int) -> int:
        return struct.unpack("<i", self.uc.mem_read(address, 4))[0]

    def rec(self, index: int = 0) -> int:
        return MGR + index * REC

    def food(self) -> int:
        return self.r32(STATE + FOOD)

    def grid(self, x: int, y: int) -> int:
        """The walk grid's value at pixel (x, y) (0x4181D0: dword (x // 10) * 170 + y // 10)."""
        return self.r32(MAP + 4 * ((x // 10) * 0xAA + y // 10))

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
        self.rand_calls += 1
        if caller in self.by_caller:
            value = self.by_caller[caller]
        elif self.forced is not None:
            value = self.forced.pop(0) if self.forced else 0
        else:
            value = self.rng.randrange(n) if 0 < n <= 0x7FFF else 0
        self._ret(value, 0)

    def _on_reward(self, *_):
        reward = struct.unpack("<i", self.uc.mem_read(self.uc.reg_read(UC_X86_REG_ESP) + 8, 4))[0]
        self.rewards.append((self.frame, reward))

    def _on_food(self, *_):
        amount = struct.unpack("<i", self.uc.mem_read(self.uc.reg_read(UC_X86_REG_ESP) + 4, 4))[0]
        self.food_log.append((self.frame, amount))

    def call(self, function: int, this: int, *args: int, count: int = 5_000_000) -> int:
        sp = STACK + 0x180000
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
    def villager(self, *, feet=(1140, 1037), age: int = 500, health: int = 80, skills: dict | None = None,
                 preference: int = 0, assigned: int = 0, likes=(), dislikes=(), sex: int = 1) -> int:
        """Villager 0, standing with its feet (record +4 + 20, +8 + 65: what the walk aims) at `feet`."""
        record = self.rec(0)
        self.uc.mem_write(record, bytes(REC))
        self.w8(record + ALIVE, 1)
        self.w32(record + HEALTH, health)
        self.w32(record + AGE, age)
        self.w32(record + PROC_AGE, age)
        self.w32(record + SEX, sex)
        for k in range(62):
            self.w32(record + LIKES + 4 * k, likes[k] if k < len(likes) else -1)
            self.w32(record + DISLIKES + 4 * k, dislikes[k] if k < len(dislikes) else -1)
        for name, off in SKILLS.items():
            self.w32(record + off, (skills or {}).get(name, 10))
        self.w32(record + PREFERENCE, preference)
        self.w32(record + ASSIGNED, assigned)
        self.w32(record + X, feet[0] - 20)
        self.w32(record + Y, feet[1] - 65)
        return record

    def feet(self) -> tuple[int, int]:
        return self.r32(self.rec(0) + X) + 20, self.r32(self.rec(0) + Y) + 65

    def queue_type(self) -> int:
        return self.r32(self.rec(0) + QUEUE)

    # -- live play ------------------------------------------------------------------------------------------------
    def step_frame(self) -> None:
        """One frame of the village screen's villager update (0x42F9FF calls 0x464CD0 once per frame)."""
        if self.farming_fixed is not None:
            self.w32(self.rec(0) + SKILLS["farming"], self.farming_fixed)
        self.call(UPDATE, MGR, count=5_000_000)
        self.frame += 1
        self.t += FRAME_MS / 1000.0

    def start_job(self, job: int) -> None:
        """Queue `job` for villager 0 now, as the dispatcher does (the job queues its steps and starts the first)."""
        self.call(job, MGR, 0)

    def run_trip(self, job: int, max_frames: int = 60_000) -> tuple[int, int]:
        """Start `job` now; frames until its food payoff, and until its step queue is empty (back to back)."""
        start = self.frame
        seen = len(self.food_log)
        self.start_job(job)
        paid = None
        while self.frame - start < max_frames:
            self.step_frame()
            if paid is None and len(self.food_log) > seen:
                paid = self.frame - start
            if self.queue_type() == 0:
                return (paid if paid is not None else -1), self.frame - start
        raise RuntimeError("the trip never ended")

    # -- catch-up -------------------------------------------------------------------------------------------------
    def catch_up_turn(self) -> None:
        """One catch-up job turn of villager 0 (the life loop calls 0x43B4D0 4 times a counted unit, with the flag
        state + 0x3046C set, 0x43BFD6..0x43BFFC)."""
        self.w8(STATE + CATCHING_UP, 1)
        try:
            self.call(CATCH_UP_TURN, WORLD, 0, count=5_000_000)
        finally:
            self.w8(STATE + CATCHING_UP, 0)

    def life_loop(self, passes: int = 1000) -> list[int]:
        """Run the world tick's life loop 0x43BA6C..0x43C0B5 (one pass gives every villager who is behind one age
        unit, +0x534 += 1 at 0x43C09A) pass after pass until no one is behind, as the tick repeats it, with each job
        turn 0x43B4D0 only counted: the villager index of every call."""
        turns: list[int] = []

        def turn(*_):
            sp = self.uc.reg_read(UC_X86_REG_ESP)
            turns.append(struct.unpack("<i", self.uc.mem_read(sp + 4, 4))[0])
            self._ret(0, 4)

        hook = self.uc.hook_add(UC_HOOK_CODE, turn, begin=CATCH_UP_TURN, end=CATCH_UP_TURN)
        try:
            for _ in range(passes):
                if not any(self.uc.mem_read(self.rec(i) + ALIVE, 1)[0] and
                           self.r32(self.rec(i) + PROC_AGE) < self.r32(self.rec(i) + AGE) and
                           self.r32(self.rec(i) + HEALTH) > 0 for i in range(256)):
                    break
                sp = STACK + 0x180000
                self.uc.mem_write(sp, bytes(0x100))
                self.uc.reg_write(UC_X86_REG_ESP, sp)
                self.uc.reg_write(UC_X86_REG_ESI, WORLD)
                self.uc.emu_start(LIFE_LOOP, LIFE_LOOP_END, count=50_000_000)
                if self.uc.reg_read(UC_X86_REG_EIP) != LIFE_LOOP_END:
                    raise RuntimeError("the life loop did not finish")
        finally:
            self.uc.hook_del(hook)
        return turns
