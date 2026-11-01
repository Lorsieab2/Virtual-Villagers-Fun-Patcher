"""The Tree of Life (VV4): run the stock game's own farming code in unicorn, frame by frame and in catch-up.

Used by tests/test_game_mechanics_farmers_vv4.py, which pins src/vv_game_mechanics_farmers_vv4.py.

What runs is the stock executable's code, unchanged:
  * the real map: the game's cmap.dat (research/game-data/vv4, copied from the game's Assets; never committed)
    written where the map loader 0x46C150 reads it (the map object 0x6C4658: a 256 x 256 grid of 8-pixel cells),
    with every area's box marked for a rescan as that loader leaves it; the piers (areas 0x60 / 0x61) opened or
    closed by Fishing Nets with the game's own calls 0x46CBD0 / 0x46CBA0, as the scene's area updater 0x46D090
    makes them (0x46D0A4..0x46D169); the area-1 detour registered by the static initializer 0x488E40 -> 0x46FC00;
  * the villager records built by their constructor 0x45EE90; the action handlers registered in the table
    0x501B30 exactly as the start-up registrars 0x44F770 / 0x44F790 do (every `push handler; push id; call
    registrar` in the image);
  * live play: the villager's per-frame update 0x465BD0 (from the villager frame 0x45FAB0, run by the manager loop
    0x466420 from the scene update 0x43F750 every frame while the speed is below 999, i.e. not paused): the step
    timers on the game clock 0x403750, the walk 0x461120 / 0x45E2C0 with the path search 0x4706B0 / 0x4705D0, the
    step starters 0x46A030, the do-action 0x45DEC0, the farming actions 99 (0x451C30), 129 (0x4331D0) and 100
    (0x4343A0 -> 101..104), the skill check 0x462A80, the job events 0x4642F0 and the food writer 0x41D920; the
    empty-queue wait and the scheduler 0x465840 -> the job chooser 0x461CC0 -> the player-task gate 0x4634D0 and
    the work dispatcher 0x4639B0;
  * catch-up: the job turn 0x465750 (the step resolver 0x464FA0) and the life tick 0x468430.

Replaced (each a call whose result the farming code does not read, or reads only as a pointer to itself):
  * rand(N) 0x4036D0 (rand() % N): a seeded uniform random number, or a forced value by call site;
  * the game clock 0x403750 (whole real seconds: time() minus an epoch, 0x403750..0x4037D7): int(emulated time);
  * the singleton getters 0x41FE70 (the game object, [0x4CB51C]) and 0x44DA20 (the text manager, [0x4DFF28]):
    the emulated objects (their real bodies only build the object on first use behind an SEH frame);
  * 0x41CA50, which rebuilds the scene's mouse hotspot list 0x4CCB20 (read only by the scene's mouse and drawing,
    0x4400AD..0x440128, 0x43F7C4, 0x445426), called when a fruit spot is taken or freed.
Not run: the villager frame's animation update 0x44DD60 on record + 0x1C74 (sprites; no step or walk reads it) and
its empty hooks 0x433BF0; sounds and text run as the stock code with no data loaded (they return without effect).
"""
from __future__ import annotations

import random
import re
import struct
from pathlib import Path

import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import (
    UC_X86_REG_DS,
    UC_X86_REG_EAX,
    UC_X86_REG_ECX,
    UC_X86_REG_EIP,
    UC_X86_REG_ES,
    UC_X86_REG_ESP,
    UC_X86_REG_FPCW,
    UC_X86_REG_FS,
    UC_X86_REG_GDTR,
    UC_X86_REG_SS,
)

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Tree of Life.exe"
CMAP = ROOT / "research" / "game-data" / "vv4" / "cmap.dat"

FRAME_MS = 33              # 1000 // 30: the frame limiter 0x40942B..0x409455, fps 30 (the settings' 0x403020, 0x402CB8)
REC = 0x2E3C
MANAGER, FIRST = 0x50E568, 0x50E5AC
GAME_PTR, LANG_PTR = 0x4CB51C, 0x4DFF28
MAP = 0x6C4658
FOOD, TECH, PUZZLES, THRESHOLDS = 0x4D6DD0, 0x4D6F5C, 0x4D8BF8, 0x4D8B20
HANDLERS = 0x501B30
REGISTRARS = (0x44F770, 0x44F790)
SET_KIND, SET_BLOCKED = 0x46CBD0, 0x46CBA0
# The tutorial: until its "Great job!" tip 0x2B2 has been seen, a failed Farming check passes once its "Darn!" tip
# 0x2D2 has been seen (0x462B27..0x462B5E).  A village past its first successful pick has seen 0x2B2.
TIPS, TIP_SEEN, TUTORIAL_TIP, TUTORIAL_FAIL_TIP = 0x4DACE0, 0x44B970, 0x2B2, 0x2D2

# The game's routines.
RAND, CLOCK = 0x4036D0, 0x403750
GAME_GET, LANG_GET = 0x41FE70, 0x44DA20
HOTSPOTS = 0x41CA50
CONSTRUCT, PLACE, POSITION = 0x45EE90, 0x45ECB0, 0x45ED00
UPDATE = 0x465BD0
DO_ACTION = 0x45DEC0
JOB_TURN, LIFE_TICK = 0x465750, 0x468430
FOOD_ADD, JOB_EVENT = 0x41D920, 0x4642F0
BERRIES, FISH, FRUIT = 99, 129, 100          # the do-action ids (handlers 0x451C30, 0x4331D0, 0x4343A0)
TASK_BERRIES, TASK_FISH = 3, 0x1C            # the drops 0x46F8DC (the bush) and 0x433553 (the fishing nets)
REWARD = {BERRIES: 13, FISH: 16, FRUIT: 15}  # the job event that credits the food (0x464464, 0x4645A4, 0x464567)
GOLDEN = 17                                  # job event 17: the Golden Fish, 8 food (0x4645E1)

# The game object.
G_BERRIES, G_DIFFICULTY, G_SPEED, G_CATCHUP = 0x170F8, 0x170F4, 0x17110, 0x171A4

# A villager record.
AGE, SEX, PROC_AGE, HEALTH, SICK, PREGNANT, TASK = 0x1B8C, 0x1B90, 0x1C3C, 0x1C40, 0x1C48, 0x1C4C, 0x1C54
SKILLS = {"farming": 0x1C5C, "parenting": 0x1C60, "healing": 0x1C64, "research": 0x1C68, "building": 0x1C6C}
PREFERENCE = 0x1C70           # the job preference: a skill index (0 Farming), -1 none
VX, VY = 0x1C9C, 0x1CA0       # the walk's velocity, hundredths of a pixel a frame
ACTIVE, ACTION = 0x1CC4, 0x1CE0
LIKES, DISLIKES = 0x1E60, 0x1E6C
GAME_OF_RECORD = 0x2E28

BIN = (1116, 1260)            # the middle of the food bin (map area 8, x 1096-1127, y 1248-1271)
STACK, HEAP, GAME, LANG, RET = 0x10000000, 0x11000000, 0x12000000, 0x13000000, 0x14000000
GDT, TEB = 0x15000000, 0x15001000


def handler_table(image: bytes, base: int) -> dict[int, tuple[int, int]]:
    """{action id: (handler, takes arguments)}: every `push handler; push id; call registrar` in the image."""
    out = {}
    for m in re.finditer(rb"\x68(.{4})(?:\x6A(.)|\x68(.{4}))\xE8(.{4})", image, re.DOTALL):
        func = struct.unpack("<I", m.group(1))[0]
        aid = m.group(2)[0] if m.group(2) is not None else struct.unpack("<I", m.group(3))[0]
        target = (base + m.end() + struct.unpack("<i", m.group(4))[0]) & 0xFFFFFFFF
        if target in REGISTRARS and 0x401000 <= func < 0x490000 and aid < 0x100:
            out[aid] = (func, REGISTRARS.index(target))
    return out


class Village:
    """The stock exe in an emulator: a village state, the real map and villager 0."""

    def __init__(self, *, seed: int = 1, speed: int = 6, berries: int = 1000, food: int = 1000,
                 solved=(6, 0xB), difficulty: int = 1, levels=(1, 1, 1, 1, 1, 1, 1, 1), tutorial_done: bool = True):
        pe = pefile.PE(str(STOCK), fast_load=True)
        base = pe.OPTIONAL_HEADER.ImageBase
        image = pe.get_memory_mapped_image()
        uc = Uc(UC_ARCH_X86, UC_MODE_32)
        uc.mem_map(base, (pe.OPTIONAL_HEADER.SizeOfImage + 0xFFFF) & ~0xFFFF)
        uc.mem_write(base, image)
        for area, n in ((STACK, 0x200000), (HEAP, 0x100000), (GAME, 0x20000), (LANG, 0x1000), (RET, 0x1000),
                        (GDT, 0x1000), (TEB, 0x1000)):
            uc.mem_map(area, n)
        uc.reg_write(UC_X86_REG_FPCW, 0x027F)
        # A thread block for the C runtime's exception frames (fs:[0]): fs is a GDT data segment based there.
        uc.mem_write(TEB, struct.pack("<7I", 0xFFFFFFFF, STACK + 0x200000, STACK, 0, 0, 0, TEB))
        uc.mem_write(GDT + 8, struct.pack("<Q", 0xFFF | ((TEB & 0xFFFFFF) << 16) | (0x92 << 40) | (0x4 << 52)
                                          | (((TEB >> 24) & 0xFF) << 56)))
        uc.mem_write(GDT + 16, struct.pack("<Q", 0xFFFF | (0x92 << 40) | (0xF << 48) | (0xC << 52)))
        uc.reg_write(UC_X86_REG_GDTR, (0, GDT, 0x20, 0))
        uc.reg_write(UC_X86_REG_FS, 1 << 3)
        for flat in (UC_X86_REG_SS, UC_X86_REG_DS, UC_X86_REG_ES):
            uc.reg_write(flat, 2 << 3)
        self.uc = uc
        self.rng = random.Random(seed)
        self.by_caller: dict[int, int] = {}       # a rand(N) call's return address -> the value it gets
        self.t = 1000.0                           # emulated real time, seconds
        self.frame = 0
        self.events: list[tuple[int, int]] = []   # (frame, job event) for each 0x4642F0 call
        self.food_log: list[tuple[int, int]] = []  # (frame, amount) for each 0x41D920 call
        for aid, (func, args) in handler_table(image, base).items():
            self.w32(HANDLERS + 8 * aid, func)
            self.w8(HANDLERS + 8 * aid + 4, args)
        self.w32(GAME_PTR, GAME)
        self.w32(LANG_PTR, LANG)
        uc.mem_write(MAP, CMAP.read_bytes())
        for k in range(100):                      # the loader 0x46C192..0x46C1A9: every area's box to be scanned
            self.w8(MAP + 0x40010 + 0x14 * k, 1)
        for i, level in enumerate(levels):        # technology levels (0x41E1C0: dword [0x4D6F5C + 4 * i])
            self.w32(TECH + 4 * i, level)
        for pid in range(40):                     # puzzle pid solved: progress >= threshold (0x438960)
            self.w32(THRESHOLDS + 4 * pid, 1)
            self.w32(PUZZLES + 8 * pid, 1 if pid in solved else 0)
        self.w32(FOOD, food)
        self.w32(GAME + G_BERRIES, berries)
        self.w32(GAME + G_SPEED, speed)
        self.w32(GAME + G_DIFFICULTY, difficulty)
        stubs = {RAND: self._rand, CLOCK: lambda: self._ret(int(self.t), 0),
                 GAME_GET: lambda: self._ret(GAME, 0), LANG_GET: lambda: self._ret(LANG, 0),
                 HOTSPOTS: lambda: self._ret(0, 0)}
        for address, stub in stubs.items():
            uc.hook_add(UC_HOOK_CODE, lambda _u, _a, _s, _d, stub=stub: stub(), begin=address, end=address)
        uc.hook_add(UC_HOOK_CODE, self._on_event, begin=JOB_EVENT, end=JOB_EVENT)
        uc.hook_add(UC_HOOK_CODE, self._on_food, begin=FOOD_ADD, end=FOOD_ADD)
        for k in range(150):
            self.call(CONSTRUCT, MANAGER + 0x44 + k * REC)
        self.call(0x46FC00, 0x7054CC)
        if tutorial_done:                         # the "Great job!" tip 0x2B2 seen (the tips' setter 0x44B970)
            self.call(TIP_SEEN, TIPS, TUTORIAL_TIP)
        nets = 0xB in solved
        for area in (0x60, 0x61):
            self.call(SET_KIND, MAP, area, 6 if nets else 5)
            self.call(SET_BLOCKED, MAP, area, 0 if nets else 1)

    # -- memory -------------------------------------------------------------------------------------------------
    def w32(self, a: int, v: int) -> None:
        self.uc.mem_write(a, struct.pack("<I", v & 0xFFFFFFFF))

    def w8(self, a: int, v: int) -> None:
        self.uc.mem_write(a, bytes([v & 0xFF]))

    def wf(self, a: int, v: float) -> None:
        self.uc.mem_write(a, struct.pack("<f", v))

    def r32(self, a: int) -> int:
        return struct.unpack("<i", self.uc.mem_read(a, 4))[0]

    def rec(self, index: int = 0) -> int:
        return FIRST + index * REC

    def food(self) -> int:
        return self.r32(FOOD)

    # -- stubs --------------------------------------------------------------------------------------------------
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
            value = self.rng.randrange(n) if 0 < n <= 0x7FFF else 0
        self._ret(value, 0)

    def _on_event(self, *_) -> None:
        self.events.append((self.frame, self.r32(self.uc.reg_read(UC_X86_REG_ESP) + 4)))

    def _on_food(self, *_) -> None:
        self.food_log.append((self.frame, self.r32(self.uc.reg_read(UC_X86_REG_ESP) + 4)))

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
    def villager(self, *, at=BIN, age: int = 500, health: int = 80, skills: dict | None = None, task: int = 0,
                 preference: int = -1, likes=(), dislikes=(), index: int = 0) -> int:
        """Villager `index`, an awake adult standing at `at` (what 0x45ED00 reports), skills as given (10 else)."""
        r = self.rec(index)
        self.w8(r + ACTIVE, 1)
        self.w32(r + AGE, age)
        self.w32(r + PROC_AGE, age)
        self.w32(r + HEALTH, health)
        self.w32(r + SEX, 1)
        self.w32(r + TASK, task)
        self.w32(r + PREFERENCE, preference)
        for name, off in SKILLS.items():
            self.wf(r + off, float((skills or {}).get(name, 10)))
        for k in range(3):
            self.w32(r + LIKES + 4 * k, likes[k] if k < len(likes) else -1)
            self.w32(r + DISLIKES + 4 * k, dislikes[k] if k < len(dislikes) else -1)
        self.w32(r + GAME_OF_RECORD, GAME)
        self.call(PLACE, r, at[0], at[1])
        return r

    def pos(self, index: int = 0) -> tuple[int, int]:
        out = HEAP + 0x1000
        self.call(POSITION, self.rec(index), out)
        return self.r32(out), self.r32(out + 4)

    def at_bin(self, index: int = 0) -> bool:
        x, y = self.pos(index)
        return 1094 <= x <= 1129 and 1246 <= y <= 1273

    def queue_type(self, index: int = 0) -> int:
        return self.r32(self.rec(index))

    # -- live play ----------------------------------------------------------------------------------------------
    def step_frame(self, index: int = 0) -> None:
        """One frame of the villager's update 0x465BD0; the emulated real time moves on 33 ms."""
        self.call(UPDATE, self.rec(index), count=200_000_000)
        self.frame += 1
        self.t += FRAME_MS / 1000.0

    def start(self, action: int, index: int = 0) -> None:
        """Start `action` as a drop or the scheduler does: the do-action 0x45DEC0 with a zeroed argument block."""
        self.uc.mem_write(HEAP + 0x2000, bytes(0x40))
        self.call(DO_ACTION, self.rec(index), action, HEAP + 0x2000)

    def run_trip(self, action: int, max_frames: int = 60_000, index: int = 0) -> tuple[int, int, list[int]]:
        """Start `action` now: (frames to its food reward or -1, frames until its queue is empty, rewards)."""
        start, seen = self.frame, len(self.events)
        self.start(action, index)
        paid = None
        while self.frame - start < max_frames:
            self.step_frame(index)
            got = [e for _, e in self.events[seen:] if e in (13, 15, 16, 17)]
            if paid is None and got:
                paid = self.frame - start
            if self.queue_type(index) == 0:
                return (paid if paid is not None else -1), self.frame - start, got
        raise RuntimeError("the trip never ended")

    # -- catch-up -----------------------------------------------------------------------------------------------
    def catch_up_turn(self, index: int = 0) -> None:
        """One catch-up job turn 0x465750, with the catch-up flag set as the life tick sets it (0x468A59)."""
        self.w8(GAME + G_CATCHUP, 1)
        try:
            self.call(JOB_TURN, self.rec(index), count=50_000_000)
        finally:
            self.w8(GAME + G_CATCHUP, 0)

    def life_tick(self, count_turns: bool = True) -> list[int]:
        """The life tick 0x468430 over every villager until no one is behind; with `count_turns` each job turn
        0x465750 is only counted (the record of every call is returned)."""
        turns: list[int] = []

        def turn(*_):
            turns.append(self.uc.reg_read(UC_X86_REG_ECX))
            self._ret(0, 0)

        hook = self.uc.hook_add(UC_HOOK_CODE, turn, begin=JOB_TURN, end=JOB_TURN) if count_turns else None
        try:
            self.call(LIFE_TICK, MANAGER, count=500_000_000)
        finally:
            if hook is not None:
                self.uc.hook_del(hook)
        return turns


def bin_trips(action: int, n: int, *, seed: int, farming: int = 89, speed: int = 6, **villager):
    """n back-to-back trips from where the previous one ended (the first from the bin), the bush kept at 1,000 and
    the Farming skill fixed: [(start position, frames to the reward or -1, frames to the end, rewards)]."""
    v = Village(seed=seed, speed=speed)
    v.villager(skills={"farming": farming}, **villager)
    out = []
    for _ in range(n):
        v.w32(GAME + G_BERRIES, 1000)
        v.wf(v.rec(0) + SKILLS["farming"], float(farming))
        start = v.pos()
        paid, done, got = v.run_trip(action)
        out.append((start, paid, done, got))
    return out


def scheduler(task: int, farming: int, hours: float, *, seed: int, berries: int = 1000, solved=(6, 0xB)):
    """A Farming-preference farmer with player task `task`, all other skills 10, food kept at 1,000 and the bush at
    `berries`, left to the game's own scheduler for `hours` real-life hours: (seconds, rewards {event: count})."""
    v = Village(seed=seed, berries=berries, solved=solved)
    r = v.villager(skills={"farming": farming}, task=task, preference=0)
    for _ in range(int(hours * 3600 * 1000 / FRAME_MS)):
        v.w32(FOOD, 1000)
        v.w32(GAME + G_BERRIES, berries)
        v.wf(r + SKILLS["farming"], float(farming))
        v.step_frame()
    counts: dict[int, int] = {}
    for _, e in v.events:
        if e in (13, 15, 16, 17):
            counts[e] = counts.get(e, 0) + 1
    return v.frame * FRAME_MS / 1000.0, counts
