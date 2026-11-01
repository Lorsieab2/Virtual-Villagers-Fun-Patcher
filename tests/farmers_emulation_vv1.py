"""A New Home (VV1): run the stock game's own farming code in unicorn, frame by frame and in catch-up.

Used by tests/test_game_mechanics_farmers_vv1.py, which pins src/vv_game_mechanics_farmers_vv1.py.

What runs is the stock executable's code, unchanged:
  * the map builder 0x414590 (the 10-pixel walk grid, 168 x 168 cells, read by 0x414200), on a village state;
  * the farming jobs: berry picking 0x441E10, crop harvesting 0x4439F0, fishing 0x43F450 (each queues its steps
    with 0x4399F0 and starts the first with 0x43DEF0);
  * live play: the per-frame action runner 0x448600 (the step timers on the game clock 0x402F70, the walk 0x445CB0
    with its obstacle detours 0x43DFC0, the step starters 0x43DEF0 / 0x445C50, the reward 0x43A230 and the food
    writer 0x41D140), the empty-queue wait and the scheduler 0x448220 -> job chooser 0x439AE0 -> work
    dispatcher 0x4472C0;
  * catch-up: the job turn 0x42E790 -> 0x439AE0 -> 0x4472C0 -> the instant step runner 0x446C70.

Replaced (each named in the docstring of the test that relies on it):
  * rand(N) 0x402F10 (rand() % N): a seeded uniform random number, or a forced value;
  * the game clock 0x402F70 (whole real seconds, time() minus the save's epoch) and time() 0x401E10: the emulated
    real time, int(seconds);
  * drawing, sound and text only: the speech bubble 0x417DF0 / 0x417C60, the particle effects 0x41AFD0, the
    tutorial popup 0x41C960, the text table 0x433970, sprintf 0x44B23D and the draw-order sort 0x439FC0 (it only
    reorders the index list at manager + 0x3DBDC).  None of them touches a villager's step queue, position,
    timers or the food (each is a call whose result the farming code does not read, or reads only as a string).
"""
from __future__ import annotations

import random
import struct
from pathlib import Path

import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - A New Home.exe"

FRAME_MS = 33              # 1000 // 30: the frame limiter 0x409118..0x409142 (fps 30 from the settings 0x402FC0)
REC = 0x3D8                # a villager record

# The game's routines.
RAND, CLOCK, TIME = 0x402F10, 0x402F70, 0x401E10
RUNNER, CATCH_UP_TURN, BUILD_MAP = 0x448600, 0x42E790, 0x414590
LIFE_LOOP, LIFE_LOOP_END = 0x42EC53, 0x42F168
BERRIES, CROPS, FISH = 0x441E10, 0x4439F0, 0x43F450
REWARD, FOOD_ADD = 0x43A230, 0x41D140
COSMETIC = {0x417DF0: 0x18, 0x417C60: 4, 0x41AFD0: 0x1C, 0x41C960: 8,   # routine -> bytes it pops (ret n)
            0x439FC0: 0}   # the draw-order sort of the index list at manager + 0x3DBDC (every 11th runner call)
TEXT, SPRINTF = 0x433970, 0x44B23D

# State offsets (a save's file offset is 4 more).
FOOD, BUSH, FIELD, FARMING_LEVEL, SPEED = 0xA2EC, 0xA2F4, 0xA2F8, 0xA2E4, 0xA318
BEACH_DONE, BEACH_PROGRESS = 0x9FB8, 0x9FB4
LEVELS, DIFFICULTY = 0xA2BC, 0xA30C        # technology levels (8 apart, Farming the 6th); 0 Easy, 1 Medium, 2 Hard
MANAGER_PTR = 0xADE8

# Villager record offsets.
X, Y, QUEUE = 0x4, 0x8, 0x44
ALIVE, HEALTH, AGE, PROC_AGE, GENDER, SICK, PREGNANT = 0x28, 0x344, 0x348, 0x34C, 0x350, 0x354, 0x358
FAMILY = 0x36C
LIKES, DISLIKES = 0x398, 0x3A8
SOURCE, PREFERENCE = 0x3B8, 0x3D0
SKILLS = {"parenting": 0x3BC, "building": 0x3C0, "farming": 0x3C4, "healing": 0x3C8, "research": 0x3CC}

STACK, MGR, STATE, MAP, BUF, WORLD, RET = (0x30000000, 0x31000000, 0x31100000, 0x31200000, 0x31300000,
                                          0x31400000, 0x31500000)


class Village:
    """The stock exe in an emulator, with one villager (index 0) and a village state built from scratch."""

    def __init__(self, *, seed: int = 1, speed: int = 6, farming_level: int = 3, beach_clean: bool = True,
                 bush: int = 100_000, field: int = 800, food: int = 1000, state: bytes | None = None):
        pe = pefile.PE(str(STOCK), fast_load=True)
        base = pe.OPTIONAL_HEADER.ImageBase
        image = pe.get_memory_mapped_image()
        uc = Uc(UC_ARCH_X86, UC_MODE_32)
        uc.mem_map(base, (len(image) + 0xFFFF) & ~0xFFFF)
        uc.mem_write(base, image)
        for area, size in ((STACK, 0x100000), (MGR, 0x40000), (STATE, 0x10000), (MAP, 0x20000), (BUF, 0x10000),
                           (WORLD, 0x1000), (RET, 0x1000)):
            uc.mem_map(area, size)
        self.uc = uc
        self.rng = random.Random(seed)
        self.forced: list[int] | None = None
        self.by_caller: dict[int, int] = {}         # a rand(N) call's return address -> the value it gets
        self.t = 1000.0                     # emulated real time, seconds
        self.frame = 0
        self.rewards: list[tuple[int, int]] = []    # (frame, reward id) for each 0x43A230 call
        self.food_log: list[tuple[int, int]] = []   # (frame, food added) for each 0x41D140 call
        self.rand_calls = 0
        if state is not None:               # a save's state: file offset 0xC on is state + 8 on
            uc.mem_write(STATE + 8, state[0xC:])
        self.w32(MGR + 0x3E010, STATE)
        self.w32(MGR + 0x3E014, MAP)
        for off in (0x3E018, 0x3E01C, 0x3E020, 0x3E024, 0x3E02C):
            self.w32(MGR + off, BUF)
        self.w32(STATE + MANAGER_PTR, MGR)
        self.w32(BUF + 0x1480, STATE)       # the hut object (manager + 0x3E024) reads the state through +0x1480 when a
        #                                     building job's reward rebuilds the huts (0x416380); not farming code
        self.w32(MAP + 0x1B904, STATE)
        self.w32(MAP + 0x1B908, BUF)
        self.w32(WORLD, STATE)              # the world object of the tick 0x42E900: [+0] state, [+4] villagers
        self.w32(WORLD + 4, MGR)
        if state is None:                   # a new village: every technology at level 1 (0x41C43E), Medium
            for level in range(6):
                self.w32(STATE + LEVELS + 8 * level, 1)
            self.w32(STATE + DIFFICULTY, 1)
        self.w32(STATE + FOOD, food)
        self.w32(STATE + BUSH, bush)
        self.w32(STATE + FIELD, field)
        self.w32(STATE + FARMING_LEVEL, farming_level)
        self.w32(STATE + SPEED, speed)
        self.w8(STATE + BEACH_DONE, 1 if beach_clean else 0)
        self.w32(STATE + BEACH_PROGRESS, 150 if beach_clean else 0)
        stubs = {RAND: self._rand, CLOCK: lambda: self._ret(int(self.t), 0), TIME: lambda: self._ret(int(self.t), 0),
                 TEXT: lambda: self._ret(BUF, 4), SPRINTF: lambda: self._ret(0, 0)}
        for address, pop in COSMETIC.items():
            stubs[address] = lambda pop=pop: self._ret(0, pop)
        for address, stub in stubs.items():
            uc.hook_add(UC_HOOK_CODE, lambda _u, _a, _s, _d, stub=stub: stub(), begin=address, end=address)
        uc.hook_add(UC_HOOK_CODE, self._on_reward, begin=REWARD, end=REWARD)
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
    def villager(self, *, feet=(1209, 1165), age: int = 500, health: int = 80, skills: dict | None = None,
                 source: int = 0, preference: int = 0, likes=(), dislikes=()) -> int:
        """Villager 0, standing with its feet (record +4 + 20, +8 + 65: what the walk aims) at `feet`."""
        record = self.rec(0)
        self.uc.mem_write(record, bytes(REC))
        self.w8(record + ALIVE, 1)
        self.w32(record + HEALTH, health)
        self.w32(record + AGE, age)
        self.w32(record + PROC_AGE, age)
        self.w32(record + GENDER, 1)
        self.w32(record + FAMILY, 10)
        for k in range(4):
            self.w32(record + LIKES + 4 * k, likes[k] if k < len(likes) else -1)
            self.w32(record + DISLIKES + 4 * k, dislikes[k] if k < len(dislikes) else -1)
        for name, off in SKILLS.items():
            self.w32(record + off, (skills or {}).get(name, 10))
        self.w32(record + SOURCE, source)
        self.w32(record + PREFERENCE, preference)
        self.w32(record + X, feet[0] - 20)
        self.w32(record + Y, feet[1] - 65)
        self.w32(self.rec(1), 0)            # villager 0's empty-queue wait (the runner reads it at record + 0x3D8)
        return record

    def feet(self) -> tuple[int, int]:
        return self.r32(self.rec(0) + X) + 20, self.r32(self.rec(0) + Y) + 65

    def queue_type(self) -> int:
        return self.r32(self.rec(0) + QUEUE)

    # -- live play ------------------------------------------------------------------------------------------------
    def step_frame(self) -> None:
        """One frame of the village screen's villager update (0x42403F calls the runner once per frame)."""
        self.call(RUNNER, MGR, count=2_000_000)
        self.frame += 1
        self.t += FRAME_MS / 1000.0

    def start_job(self, job: int) -> None:
        """Queue `job` for villager 0 as the scheduler does: it zeroes the detour count (record +0x40, 0x44823B)
        before the chooser and dispatcher queue the job (a walk gives up after 15 detours, 0x43DFE9)."""
        self.w32(self.rec(0) + 0x40, 0)
        self.call(job, MGR, 0)

    def run_trip(self, job: int, max_frames: int = 40_000) -> tuple[int, int]:
        """Start `job` now; frames until its food reward, and until its step queue is empty (back to back)."""
        start = self.frame
        seen = len(self.rewards)
        self.start_job(job)
        paid = None
        while self.frame - start < max_frames:
            self.step_frame()
            if paid is None and len(self.rewards) > seen:
                paid = self.frame - start
            if self.queue_type() == 0:
                return (paid if paid is not None else -1), self.frame - start
        raise RuntimeError("the trip never ended")

    # -- catch-up -------------------------------------------------------------------------------------------------
    def catch_up_turn(self) -> None:
        """One catch-up job turn of villager 0 (the life loop calls 0x42E790 5 times a counted unit, 0x42F10A)."""
        self.call(CATCH_UP_TURN, WORLD, 0, count=5_000_000)

    def life_loop(self) -> list[int]:
        """Run the world tick's life loop 0x42EC53..0x42F168 (every villager's uncounted units, one at a time, until
        no one is behind), with each job turn 0x42E790 only counted: the villager index of every call."""
        turns: list[int] = []

        def turn(*_):
            sp = self.uc.reg_read(UC_X86_REG_ESP)
            turns.append(struct.unpack("<i", self.uc.mem_read(sp + 4, 4))[0])
            self._ret(0, 4)

        hook = self.uc.hook_add(UC_HOOK_CODE, turn, begin=CATCH_UP_TURN, end=CATCH_UP_TURN)
        try:
            sp = STACK + 0x80000
            self.uc.mem_write(sp, bytes(0x100))
            self.uc.reg_write(UC_X86_REG_ESP, sp)
            self.uc.reg_write(UC_X86_REG_ESI, WORLD)
            self.uc.emu_start(LIFE_LOOP, LIFE_LOOP_END, count=20_000_000)
            if self.uc.reg_read(UC_X86_REG_EIP) != LIFE_LOOP_END:
                raise RuntimeError("the life loop did not finish")
        finally:
            self.uc.hook_del(hook)
        return turns
