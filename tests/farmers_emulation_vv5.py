"""New Believers (VV5): run the stock game's own farming code in unicorn, frame by frame and in catch-up.

Used by tests/test_game_mechanics_farmers_vv5.py, which pins src/vv_game_mechanics_farmers_vv5.py.

What runs is the stock executable's code, unchanged, from start-up on:
  * the C runtime's static initialisers (the 73 entries of the initialiser table 0x495468..0x49558C: every global
    object's constructor, the behaviour table 0x5475C8 that 0x463F90 fills, the villager table 0x554148);
  * the village manager 0x425950 (0x17E3C bytes, its constructor 0x425880) and the stage-1 loaders the loading
    screen runs (0x423E12..0x423E8F): among them the walk map 0x4775B0 (lcmap.dat, a 320 x 320 grid of 4-byte cells
    at 0x718EE8), the waypoints 0x47AB20 (wpts.dat), the projects 0x43AC30 and the animations 0x451180 (anims.dat,
    animpts.dat);
  * a new village: the manager's reset 0x4246A0 (the one Start Over and a new slot run) and one believer made by the
    stock creator 0x471E20 -> 0x46FAD0 -> 0x4681F0;
  * live play: the villagers' per-frame update 0x471EB0 (called once a frame from 0x442AE7 while not paused): the
    step-timer check 0x475460, the step starter 0x473590, the per-frame step runner 0x473B30 (the walk 0x468FF0 /
    0x469250 with its path 0x47AE30, the skill check 0x46B270, the work payoffs 0x46CE60 and the food writer
    0x41EB40), and, whenever a villager's queue is empty, the scheduler 0x46F070 -> chooser 0x46A3C0 -> work
    dispatcher 0x46C540 or the player's job 0x46BCF0;
  * catch-up: the job turn 0x46E8E0 (chooser 0x46A3C0, dispatcher 0x46C540 or 0x46BCF0, the instant step runner
    0x46E020) and the life pass 0x472C90.

Replaced (each named in the docstring of the test that relies on it):
  * the game's RNG(n) 0x403660 (rand() % n): a seeded uniform value, or a value forced for one call site; the C
    runtime's rand 0x47CFD8 likewise;
  * time: GetSystemTimeAsFileTime / QueryPerformanceCounter / GetTickCount / SDL_GetTicks give the emulated real time,
    so the game's own real clock 0x4036E0 (whole seconds, time() minus the save's base) counts emulated seconds;
  * the C runtime's plumbing a single-threaded run never needs: its locks _lock 0x483AFE / _unlock 0x483A26, atexit
    0x47E76E, the per-thread block (_getptd 0x4817B5, _getptd_noexit 0x48173E), _localtime64 0x47C946 (the emulated
    time as UTC; the new village's reset 0x477240 asks it on some seeds), the heap (HeapAlloc and friends: a bump
    allocator), and its files (fopen 0x47D1AC, fread 0x47D567, fclose 0x47D06C: the four data files from
    research/game-data/vv5, nothing else);
  * drawing and sound only: every SDL2, SDL2_image and FMOD import returns nothing, except that an image load
    (IMG_Load) or a new surface returns a stand-in surface of a fixed size with one shared blank pixel buffer.
    Nothing a villager's walk, waits, checks or payoffs read comes from an image: with each image's real size the
    trips came out frame for frame the same (the optional test needs research/game-data/vv5/image_sizes.json).
Not run: the 2-second village update 0x442581..0x442A35 (ageing, eating, weather, island events), so it never
rains and nobody ages, eats or falls sick during a live measurement.
"""
from __future__ import annotations

import json
import random
import struct
import time
from pathlib import Path

import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import (UC_X86_REG_DS, UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EIP, UC_X86_REG_ES,
                               UC_X86_REG_ESP, UC_X86_REG_FPCW, UC_X86_REG_FS, UC_X86_REG_GDTR, UC_X86_REG_SS)

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - New Believers.exe"
DATA = ROOT / "research" / "game-data" / "vv5"
DATA_FILES = ("lcmap.dat", "wpts.dat", "anims.dat", "animpts.dat")
IMAGE_SIZES = DATA / "image_sizes.json"


def available() -> bool:
    return STOCK.is_file() and all((DATA / name).is_file() for name in DATA_FILES)


FRAME_MS = 33              # 1000 // 30: the frame limiter 0x40965B..0x409685 (fps 30: the settings' slot 0x402FB0)

# The game's routines.
RAND, CRT_RAND, CLOCK = 0x403660, 0x47CFD8, 0x4036E0
VILLAGER_UPDATE, SCHEDULER, CHOOSER, DISPATCH, PLAYER_JOB = 0x471EB0, 0x46F070, 0x46A3C0, 0x46C540, 0x46BCF0
SET_BEHAVIOUR, CLEAR_QUEUE, CATCH_UP_TURN, LIFE_PASS = 0x465580, 0x473440, 0x46E8E0, 0x472C90
SKILL_CHECK, WORK_EVENT, FOOD_ADD = 0x46B270, 0x46CE60, 0x41EB40
NEW_VILLAGE, MAKE_VILLAGER, MANAGER = 0x4246A0, 0x471E20, 0x425950
LOADERS = ((0x431410, 0x51D6C0), (0x413AD0, 0x4DBFC8), (0x4775B0, 0x718EE8), (0x421FC0, 0x4DC960),
           (0x478720, 0x77DC7C), (0x41D400, 0x4DE000), (0x475F30, 0x710948), (0x43AC30, 0x51E008),
           (0x476930, 0x718988), (0x46F870, 0x554148), (0x47AB20, 0x77DEE4), (0x47ABE0, 0x77DF18),
           (0x451180, 0x5258B8))
INITTERM = (0x495468, 0x49558C)

# The farming behaviours (0x465580's ids; their routines 0x457910, 0x457C80, 0x463B20) and their payoffs.
NONI, CROPS, FISH = 0x6C, 0x6D, 0xE9
PAYOFF = {0x46D000: NONI, 0x46D113: CROPS, 0x46D7A1: FISH}   # 0x41EB40's return address -> the trip
# The job the player gave (record +0x1C54) by dropping the villager on a source: 0x46BCF0's table 0x46C4B8.
PLAYER_NONI, PLAYER_CROPS, PLAYER_FISH = 3, 5, 28

# Globals.
VILLAGERS = 0x554148       # the villager table; believer i's fields at +0x48 + i * 0x2F44
V0 = VILLAGERS + 0x48
FOOD = 0x51D34C            # the food store (an object whose first dword is the food)
PROGRESS, THRESHOLD = 0x51E008, 0x51DF30   # project n: progress at +8n, done at the threshold +4n (0x43AE80)
TECH = 0x51D5CC            # tech levels (0x423600): 0 Science, 1 Medicine, 2 Learning, 3 Construction, 4 Food Mastery
GRANARY, HUNGRY_TOTEM, HYDRO_FARM, LAKE = 2, 3, 5, 10

# Manager offsets.
NONI_LEFT, CROPS_LEFT, DIFFICULTY, SPEED, CATCH_UP = 0x17D58, 0x17D5C, 0x17D54, 0x17D7C, 0x17E10

# Villager field offsets.
X, Y = 0x1C98, 0x1C9C
VX, VY = 0x1CA0, 0x1CA4
IDLE_TIMER = 0x1B84
AGE, PROC_AGE, HEALTH, SICK, PREGNANT = 0x1B8C, 0x1C3C, 0x1C40, 0x1C48, 0x1C4C
PLAYER_JOB_FIELD, PREFERENCE, SKILLS, LIKES, DISLIKES = 0x1C54, 0x1C74, 0x1C5C, 0x1F5C, 0x1F68
BEHAVIOUR, HEATHEN = 0x1D10, 0x1CEC
SKILL = {"farming": 0, "parenting": 1, "healing": 2, "research": 3, "building": 4, "devotion": 5}
STEP = 0x58                # a queued step: type at +0, its parameters from +4, its time at +0x54

STACK, HEAP, STUBS, RET, TEB, GDT, PIXELS, FLAG = (0x20000000, 0x30000000, 0x2F000000, 0x2FF00000, 0x2E000000,
                                                    0x2E100000, 0x40000000, 0x2FF00800)
STDCALL = {"HeapFree": 12, "HeapSize": 12, "GetProcessHeap": 0, "EnterCriticalSection": 4,
           "LeaveCriticalSection": 4, "InitializeCriticalSection": 4, "DeleteCriticalSection": 4,
           "InterlockedIncrement": 4, "InterlockedDecrement": 4, "InterlockedExchange": 8,
           "InterlockedCompareExchange": 12, "GetCurrentThreadId": 0, "GetCurrentProcessId": 0, "GetLastError": 0,
           "SetLastError": 4, "TlsGetValue": 4, "TlsSetValue": 8, "GetModuleHandleA": 4, "Sleep": 4,
           "GetTimeZoneInformation": 4, "VirtualAlloc": 16, "VirtualFree": 12, "CloseHandle": 4}


class Village:
    """The stock exe in an emulator: a new village with one believer (villager 0, fields at V0)."""

    def __init__(self, *, seed: int = 1, speed: int = 6, food: int = 1000, noni: int = 1000, crops: int = 800,
                 projects=(GRANARY, HUNGRY_TOTEM, HYDRO_FARM, LAKE), learning: int = 1, image_sizes: bool = False):
        pe = pefile.PE(str(STOCK), fast_load=True)
        pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]])
        base = pe.OPTIONAL_HEADER.ImageBase
        size = (pe.OPTIONAL_HEADER.SizeOfImage + 0xFFFF) & ~0xFFFF
        uc = Uc(UC_ARCH_X86, UC_MODE_32)
        uc.mem_map(base, size)
        uc.mem_write(base, pe.get_memory_mapped_image()[:size])
        for area, length in ((STACK, 0x200000), (HEAP, 0x8000000), (STUBS, 0x10000), (RET, 0x1000),
                             (TEB, 0x10000), (GDT, 0x1000), (PIXELS, 0x2000000)):
            uc.mem_map(area, length)
        uc.reg_write(UC_X86_REG_FPCW, 0x027F)     # the C runtime's start-up precision (53 bits)
        self.uc = uc
        self._segments()
        self.heap_top = HEAP + 0x1000
        self.rng = random.Random(seed)
        self.by_caller: dict[int, object] = {}   # a rand(n) call's return address -> its value (or a function of n)
        self.rand_log: list | None = None
        self.t = 1_000_000.0                      # emulated real time, seconds
        self.frame = 0
        self.food_log: list[tuple[int, int, int]] = []   # (frame, amount, return address) for each food change
        self.files: dict[int, list] = {}
        self.next_file = 0x2F008000
        self.sizes = ({k: tuple(v) for k, v in json.loads(IMAGE_SIZES.read_text()).items()}
                      if image_sizes else None)
        self.stub_names = {}
        k = 0
        for entry in pe.DIRECTORY_ENTRY_IMPORT:
            for imp in entry.imports:
                address = STUBS + 0x10 * k
                k += 1
                self.stub_names[address] = (entry.dll.decode(),
                                            imp.name.decode() if imp.name else f"#{imp.ordinal}")
                uc.mem_write(imp.address, struct.pack("<I", address))
        uc.hook_add(UC_HOOK_CODE, self._import, begin=STUBS, end=STUBS + 0xFFFF)
        self.w32(0x7B0A44, 1)                     # the C runtime's heap: made (_crtheap), the system heap (1)
        self.w32(0x7B0C58, 1)
        self.ptd = self.alloc(0x1000)
        stubs = {0x483AFE: lambda: self._ret(0, 0), 0x483A26: lambda: self._ret(0, 0),
                 0x47E76E: lambda: self._ret(self.arg(0), 0), 0x4817B5: lambda: self._ret(self.ptd, 0),
                 0x48173E: lambda: self._ret(self.ptd, 0), 0x47C946: self._localtime,
                 0x47D1AC: self._fopen, 0x47D567: self._fread, 0x47D06C: lambda: self._ret(0, 0),
                 RAND: self._rand, CRT_RAND: lambda: self._ret(self.rng.randrange(0x8000), 0)}
        for address, stub in stubs.items():
            uc.hook_add(UC_HOOK_CODE, lambda _u, _a, _s, _d, stub=stub: stub(), begin=address, end=address)
        uc.hook_add(UC_HOOK_CODE, self._on_food, begin=FOOD_ADD, end=FOOD_ADD)

        for a in range(*INITTERM, 4):             # the static initialisers, in the C runtime's order
            if self.ru32(a):
                self.call(self.ru32(a))
        self.mgr = self.call(MANAGER)
        for routine, this in LOADERS:
            self.call(routine, this)
        self.call(NEW_VILLAGE, self.mgr)
        self.call(MAKE_VILLAGER, VILLAGERS, 1, 0, 5, 0, 600)
        for n in projects:
            self.w32(PROGRESS + 8 * n, self.r32(THRESHOLD + 4 * n))
        self.w32(TECH + 4 * 2, learning)
        self.w32(self.mgr + SPEED, speed)
        self.w32(FOOD, food)
        self.w32(self.mgr + NONI_LEFT, noni)
        self.w32(self.mgr + CROPS_LEFT, crops)

    # -- the machine ------------------------------------------------------------------------------------------
    def _segments(self) -> None:
        """A GDT with a flat data segment and one for fs: the C runtime's exception frames read fs:[0]."""
        def entry(b, limit, access, flags):
            return struct.pack("<Q", (limit & 0xFFFF) | ((b & 0xFFFFFF) << 16) | (access << 40)
                               | (((limit >> 16) & 0xF) << 48) | (flags << 52) | (((b >> 24) & 0xFF) << 56))
        uc = self.uc
        uc.mem_write(TEB, struct.pack("<I", 0xFFFFFFFF))
        uc.mem_write(TEB + 0x18, struct.pack("<I", TEB))
        uc.mem_write(GDT + 8 * 3, entry(TEB, 0xFFFF, 0xF3, 0x4))
        uc.mem_write(GDT + 8 * 4, entry(0, 0xFFFFF, 0x93, 0xC))
        uc.reg_write(UC_X86_REG_GDTR, (0, GDT, 0x100, 0))
        uc.reg_write(UC_X86_REG_FS, (3 << 3) | 3)
        for reg in (UC_X86_REG_SS, UC_X86_REG_DS, UC_X86_REG_ES):
            uc.reg_write(reg, 4 << 3)

    def w32(self, address: int, value: int) -> None:
        self.uc.mem_write(address, struct.pack("<I", value & 0xFFFFFFFF))

    def w8(self, address: int, value: int) -> None:
        self.uc.mem_write(address, bytes([value & 0xFF]))

    def wf(self, address: int, value: float) -> None:
        self.uc.mem_write(address, struct.pack("<f", value))

    def r32(self, address: int) -> int:
        return struct.unpack("<i", self.uc.mem_read(address, 4))[0]

    def ru32(self, address: int) -> int:
        return struct.unpack("<I", self.uc.mem_read(address, 4))[0]

    def r8(self, address: int) -> int:
        return self.uc.mem_read(address, 1)[0]

    def rf(self, address: int) -> float:
        return struct.unpack("<f", self.uc.mem_read(address, 4))[0]

    def alloc(self, n: int) -> int:
        address = self.heap_top
        self.heap_top = (self.heap_top + n + 15) & ~15
        self.uc.mem_write(address, bytes(n))
        return address

    def arg(self, i: int) -> int:
        return struct.unpack("<I", self.uc.mem_read(self.uc.reg_read(UC_X86_REG_ESP) + 4 + 4 * i, 4))[0]

    def _ret(self, value: int, pop: int) -> None:
        sp = self.uc.reg_read(UC_X86_REG_ESP)
        back = struct.unpack("<I", self.uc.mem_read(sp, 4))[0]
        self.uc.reg_write(UC_X86_REG_EAX, value & 0xFFFFFFFF)
        self.uc.reg_write(UC_X86_REG_ESP, sp + 4 + pop)
        self.uc.reg_write(UC_X86_REG_EIP, back)

    def call(self, function: int, this: int = 0, *args: int, count: int = 50_000_000) -> int:
        sp = STACK + 0x1F0000
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

    def cstr(self, address: int, n: int = 260) -> str:
        return bytes(self.uc.mem_read(address, n)).split(b"\0")[0].decode("latin-1")

    # -- stubs ------------------------------------------------------------------------------------------------
    def _rand(self) -> None:
        sp = self.uc.reg_read(UC_X86_REG_ESP)
        caller, n = struct.unpack("<Ii", self.uc.mem_read(sp, 8))
        if caller in self.by_caller:
            value = self.by_caller[caller]
            value = value(n) if callable(value) else value
        else:
            value = self.rng.randrange(n) if 0 < n <= 0x7FFF else 0
        if self.rand_log is not None:
            self.rand_log.append((caller, n, value))
        self._ret(value, 0)

    def _localtime(self) -> None:
        """_localtime64 0x47C946 (the C runtime's time zone code asks Windows): the emulated time, as UTC."""
        tm = time.gmtime(self.r32(self.arg(0)))
        buf = self.ptd + 0x800
        self.uc.mem_write(buf, struct.pack("<9i", tm.tm_sec, tm.tm_min, tm.tm_hour, tm.tm_mday, tm.tm_mon - 1,
                                           tm.tm_year - 1900, (tm.tm_wday + 1) % 7, tm.tm_yday - 1, 0))
        self._ret(buf, 0)

    def _on_food(self, *_) -> None:
        if self.uc.reg_read(UC_X86_REG_ECX) == FOOD:
            sp = self.uc.reg_read(UC_X86_REG_ESP)
            self.food_log.append((self.frame, self.r32(sp + 4), self.ru32(sp)))

    def _fopen(self) -> None:
        name = self.cstr(self.arg(0)).replace("\\", "/").split("/")[-1].lower()
        if name in DATA_FILES:
            handle = self.next_file
            self.next_file += 0x10
            self.files[handle] = [(DATA / name).read_bytes(), 0]
            self._ret(handle, 0)
        else:
            self._ret(0, 0)

    def _fread(self) -> None:
        buf, size, count, handle = (self.arg(i) for i in range(4))
        data, pos = self.files[handle]
        n = min(count, (len(data) - pos) // size if size else 0)
        self.uc.mem_write(buf, data[pos:pos + n * size])
        self.files[handle][1] = pos + n * size
        self._ret(n, 0)

    def _surface(self, w: int, h: int) -> int:
        s, fmt = self.alloc(0x40), self.alloc(0x40)
        self.w32(fmt + 8, 32)
        for off, value in ((4, fmt), (8, w), (0xC, h), (0x10, w * 4), (0x14, PIXELS)):
            self.w32(s + off, value)
        return s

    def _import(self, _uc, address, _size, _data) -> None:
        dll, name = self.stub_names[address]
        now = self.t
        if dll.upper().startswith("SDL"):
            value = 0
            if name == "IMG_Load":
                if self.sizes is None:
                    value = self._surface(64, 64)
                else:
                    size = self.sizes.get(self.cstr(self.arg(0)).replace("\\", "/").split("/")[-1].lower())
                    value = self._surface(*size) if size else 0
            elif name == "SDL_CreateRGBSurface":
                value = self._surface(self.arg(1), self.arg(2))
            elif name == "SDL_ConvertSurface" and self.arg(0):
                value = self._surface(self.r32(self.arg(0) + 8), self.r32(self.arg(0) + 0xC))
            elif name in ("SDL_CreateTexture", "SDL_CreateRenderer", "SDL_CreateWindow", "SDL_AllocFormat",
                          "SDL_RWFromFile", "SDL_RWFromMem"):
                value = self.alloc(0x40)
            elif name == "SDL_GetTicks":
                value = int(now * 1000)
            self._ret(value, 0)
        elif dll.upper().startswith("FMOD"):
            self._ret(0, 0)
        elif name == "HeapAlloc":
            self._ret(self.alloc(self.arg(2)), 12)
        elif name == "HeapReAlloc":
            old, n = self.arg(2), self.arg(3)
            new = self.alloc(n)
            if old:
                self.uc.mem_write(new, bytes(self.uc.mem_read(old, n)))
            self._ret(new, 16)
        elif name == "GetSystemTimeAsFileTime":
            self.uc.mem_write(self.arg(0), struct.pack("<Q", int((now + 11644473600) * 10_000_000)))
            self._ret(0, 4)
        elif name == "QueryPerformanceCounter":
            self.uc.mem_write(self.arg(0), struct.pack("<Q", int(now * 1e6)))
            self._ret(1, 4)
        elif name == "GetTickCount":
            self._ret(int(now * 1000), 0)
        elif name == "GetVersionExA":
            self.uc.mem_write(self.arg(0) + 4, struct.pack("<IIII", 5, 1, 2600, 2))
            self._ret(1, 4)
        elif name in ("GetModuleFileNameA", "GetCurrentDirectoryA", "SHGetSpecialFolderPathA"):
            text = b"C:\\vv5\\game.exe\0" if name == "GetModuleFileNameA" else b"C:\\vv5\0"
            self.uc.mem_write(self.arg(1), text)
            self._ret(1 if name == "SHGetSpecialFolderPathA" else len(text) - 1,
                      {"GetModuleFileNameA": 12, "GetCurrentDirectoryA": 8, "SHGetSpecialFolderPathA": 16}[name])
        elif name in ("GetFileAttributesA", "CreateDirectoryA"):
            self._ret(0x10 if name == "GetFileAttributesA" else 1, 4 if name == "GetFileAttributesA" else 8)
        elif name == "GetPrivateProfileIntA":
            self._ret(self.arg(2), 16)
        elif name == "GetPrivateProfileStringA":
            if self.arg(4):
                self.uc.mem_write(self.arg(3), b"\0")
            self._ret(0, 24)
        elif name in STDCALL:
            self._ret(0 if name.startswith("Interlocked") or name == "GetLastError" else 1, STDCALL[name])
        else:
            raise RuntimeError(f"unexpected import {dll}!{name}")

    # -- the villager ---------------------------------------------------------------------------------------------
    def villager(self, *, age: int = 600, health: int = 90, skills: dict | None = None, preference: int = 0,
                 player_job: int = 0, likes=(), dislikes=(), sick: bool = False) -> int:
        """Villager 0 as a plain adult believer: Farming preference (job 0), no likes or dislikes, nothing queued."""
        v = V0
        self.w32(v + AGE, age)
        self.w32(v + PROC_AGE, age)
        self.w32(v + HEALTH, health)
        self.w8(v + SICK, 1 if sick else 0)
        self.w32(v + PREGNANT, 0)
        for name, index in SKILL.items():
            self.wf(v + SKILLS + 4 * index, float((skills or {}).get(name, 10)))
        self.w32(v + PREFERENCE, preference)
        self.w32(v + PLAYER_JOB_FIELD, player_job)
        for k in range(3):
            self.w32(v + LIKES + 4 * k, likes[k] if k < len(likes) else -1)
            self.w32(v + DISLIKES + 4 * k, dislikes[k] if k < len(dislikes) else -1)
        self.call(CLEAR_QUEUE, v)
        self.w32(v + IDLE_TIMER, 0)
        return v

    def feet(self) -> tuple[int, int]:
        return self.r32(V0 + X), self.r32(V0 + Y)

    def step_type(self) -> int:
        return self.r32(V0)

    def queue(self) -> list[int]:
        return [t for t in (self.r32(V0 + STEP * k) for k in range(80)) if t]

    # -- live play ----------------------------------------------------------------------------------------------
    def step_frame(self) -> None:
        """One frame of the village screen: the villagers' update 0x471EB0 (0x442AE7), then 33 ms pass."""
        self.call(VILLAGER_UPDATE, VILLAGERS, count=20_000_000)
        self.frame += 1
        self.t += FRAME_MS / 1000.0

    def start(self, behaviour: int) -> None:
        """Start a farming trip as the dispatcher does (0x46CB18 -> 0x465580: the behaviour queues its steps)."""
        self.w8(FLAG, 0)
        self.call(SET_BEHAVIOUR, V0, behaviour, FLAG)

    def run_trip(self, behaviour: int, max_frames: int = 30_000) -> tuple[int, int]:
        """Start `behaviour` now; frames until its food is credited (-1: none), and until its queue is empty."""
        begin, seen = self.frame, len(self.food_log)
        self.start(behaviour)
        paid = None
        while self.frame - begin < max_frames:
            self.step_frame()
            if paid is None and any(PAYOFF.get(c) == behaviour for _, _, c in self.food_log[seen:]):
                paid = self.frame - begin
            if self.step_type() == 0:
                return (paid if paid is not None else -1), self.frame - begin
        raise RuntimeError("the trip never ended")

    # -- catch-up -------------------------------------------------------------------------------------------------
    def catch_up_turn(self) -> None:
        """One catch-up job turn of villager 0 (0x473311..0x473326 call 0x46E8E0 4 times a counted unit), with the
        catch-up flag set as 0x47330A sets it."""
        self.w8(self.mgr + CATCH_UP, 1)
        try:
            self.call(CATCH_UP_TURN, V0)
        finally:
            self.w8(self.mgr + CATCH_UP, 0)

    def life_pass(self) -> list[int]:
        """Run the life pass 0x472C90 (every believer's uncounted units, until no one is behind), with each job
        turn 0x46E8E0 only counted: the villager fields address of every call."""
        turns: list[int] = []

        def turn(*_):
            turns.append(self.uc.reg_read(UC_X86_REG_ECX))
            self._ret(0, 0)

        hook = self.uc.hook_add(UC_HOOK_CODE, turn, begin=CATCH_UP_TURN, end=CATCH_UP_TURN)
        try:
            self.call(LIFE_PASS, VILLAGERS)
        finally:
            self.uc.hook_del(hook)
        return turns
