"""Builders and healers: the behaviour patches act about three times in four,
once per decision -- run from the games' real callers.

The owner: "For all 5 games there should still be a chance of doing other
things too like stock.  The 'Fix Huts' and 'Builder Action Fixes' patch (and
any other patch that increases certain behaviors) should increase the
LIKELIHOOD of villagers doing that action, not 100% replaces them" -- 75%,
"applied ONCE PER DECISION": one roll each time the game chooses what a
builder or healer does; if it passes the patches act together, if it fails
the stock game decides that turn unchanged.  And option A: "where a stock
random roll says 'not this time' but construction is available, the builder
goes STRAIGHT INTO that construction" in all five games.

Everything here is EMULATED FROM THE GAME'S OWN CALLER: each run starts at
the executable's own `call` of its idle scheduler (A New Home 0x4487C8, The
Lost Children 0x464E9C) or at the head of its own retry loop (The Secret City
0x45C380, The Tree of Life 0x465B13, New Believers 0x46F3D3), in the
executable the patcher renders for the selected rows (Origins base + Builders
Fix Huts When Idle + Builders and Healers Work First + Healers Study Plants
Regardless of Food; Builder Action Fixes where named), with the test builds of
the three companions mapped, their detours written where their install
routines write them, and their kernel32 imports answered by name.  The
scheduler, the Building dispatcher, every patched site and every companion
stub run as machine code; only leaf game routines (the RNG, string copies,
the job pickers, hut/project state tests, the job starters) are scripted,
and ANY call into the executable that is neither scripted nor declared to
run for real stops the run with an error -- so a path the test did not
anticipate cannot pass silently.

Pinned:

* liveness: each patched site is reached from the real caller with the state
  that should reach it (the site addresses are recorded as they execute);
* forced pass: the patched behaviour happens -- including option A (a failed
  stock construction roll goes straight into the construction) in VV1, VV2,
  VV4 and VV5;
* forced fail: every patched site behaves as the unpatched executable -- the
  same scripted inputs give the same job started (or none), compared against
  a run of the stock executable with the stock bytes;
* one decision draws one roll however many patched sites it reaches, and
  The Secret City / Tree of Life / New Believers retry loop continues the
  same decision (and never carries it to another villager or loop);
* with the real generator, the share of decisions the patches take is ~75%.
"""
from __future__ import annotations

import json
import random
import struct
import sys
import unittest
from pathlib import Path

import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc, UcError
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDI,
    UC_X86_REG_EDX, UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
TEST_DLLS = {
    "fix_huts": ROOT / "tests" / "test_dlls" / "VVFP Fix Huts.test.dll",
    "work_first": ROOT / "tests" / "test_dlls" / "VVFP Work First.test.dll",
    "healers": ROOT / "tests" / "test_dlls" / "VVFP Healers Study.test.dll",
}
MODULE_FILE = {"fix_huts": "VVFP Fix Huts.dll", "work_first": "VVFP Work First.dll",
               "healers": "VVFP Healers Study.dll"}
BASES = {"fix_huts": 0x10000000, "work_first": 0x11000000, "healers": 0x12000000}
TEST_BUILD_ABSENT = "test builds are not in the release source archive (tests/test_dlls)"
TEST_BUILDS_PRESENT = all(p.is_file() for p in TEST_DLLS.values())
STOCK = {g: ROOT / "research" / "stock-executables" / n for g, n in (
    ("vv1", "Virtual Villagers - A New Home.exe"), ("vv2", "Virtual Villagers - The Lost Children.exe"),
    ("vv3", "Virtual Villagers - The Secret City.exe"), ("vv4", "Virtual Villagers - The Tree of Life.exe"),
    ("vv5", "Virtual Villagers - New Believers.exe"))}
GAME_NO = {"vv1": 1, "vv2": 2, "vv3": 3, "vv4": 4, "vv5": 5}

STACK_TOP = 0x0F000000
HALT = 0x0E000000               # a hlt for export calls
IMPORTS = 0x7C000000            # kernel32 stand-ins
VILLAGE = 0x20000000
STATE = 0x30000000
OBJ = 0x38000000                # VV4/VV5 villager object
RECORD = 0x3A000000             # VV3/VV4/VV5 villager record
STRINGS = 0x3F000000
INDEX = 7

STDCALL_BYTES = {"GetModuleHandleA": 4, "LoadLibraryA": 4, "GetProcAddress": 8,
                 "GetModuleFileNameA": 12, "lstrcpyA": 8, "VirtualQuery": 12, "VirtualProtect": 16,
                 "FlushInstructionCache": 12, "GetCurrentProcess": 0}

FORCE_REAL, FORCE_PASS, FORCE_FAIL = 0, 1, 2


def _rows(game: str, baf: bool) -> list[str]:
    rows = [f"{game}_enable_origins_exclusive_features", f"{game}_builders_fix_huts",
            f"{game}_builders_and_healers_work_first"]
    if game in ("vv1", "vv2"):
        rows.append(f"{game}_healers_study_regardless_of_food")
    if baf:
        rows.append("vv1_builder_action_fixes")
    return rows


_RENDERED: dict[tuple, bytes] = {}


def rendered(game: str, rows: tuple[str, ...]) -> bytes:
    """The executable the patcher writes for `rows` (stock mode); () = stock."""
    key = (game, rows)
    if key not in _RENDERED:
        if not rows:
            _RENDERED[key] = STOCK[game].read_bytes()
        else:
            import vv_fun_patcher as vfp
            build = next(b for b in vfp.load_builds() if b.id == game)
            data, _ = vfp.render_patched_bytes(STOCK[game], build, "stock", list(rows))
            _RENDERED[key] = bytes(data)
    return _RENDERED[key]


_IMAGES: dict[tuple, tuple] = {}


def _image(key, load, base: int):
    if (key, base) not in _IMAGES:
        pe = load()
        if pe.OPTIONAL_HEADER.ImageBase != base:
            pe.relocate_image(base)
        image = bytearray(pe.get_memory_mapped_image(ImageBase=base))
        exports = {}
        if hasattr(pe, "DIRECTORY_ENTRY_EXPORT"):
            exports = {e.name.decode(): base + e.address for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name}
        imports = []
        if hasattr(pe, "DIRECTORY_ENTRY_IMPORT"):
            for entry in pe.DIRECTORY_ENTRY_IMPORT:
                for imp in entry.imports:
                    imports.append((imp.name.decode() if imp.name else f"#{imp.ordinal}", imp.address))
        _IMAGES[(key, base)] = (bytes(image), exports, imports)
    return _IMAGES[(key, base)]


class UnscriptedCall(AssertionError):
    pass


class Leaf:
    """A scripted game routine: `nargs` stack arguments, callee-cleaned
    unless `cdecl`; fn(machine, args, ecx) -> eax."""

    def __init__(self, nargs: int, fn, cdecl: bool = False, name: str = "", out: bool = False):
        self.nargs, self.fn, self.cdecl, self.name, self.out = nargs, fn, cdecl, name, out


class Machine:
    """One emulated game process (see the module docstring)."""

    def __init__(self, game: str, exe: bytes, modules=("fix_huts", "work_first", "healers"),
                 loaded=None):
        self.game = game
        self.mu = mu = Uc(UC_ARCH_X86, UC_MODE_32)
        self.import_stub: dict[int, str] = {}
        self.exports: dict[str, dict[str, int]] = {}
        self.loaded = set(modules if loaded is None else loaded)
        mu.mem_map(IMPORTS, 0x10000)
        self._next_stub = IMPORTS
        img, _, imports = _image((game, exe), lambda: pefile.PE(data=exe), 0x400000)
        img = bytearray(img)
        self._redirect(img, imports, 0x400000)
        mu.mem_map(0x400000, (len(img) + 0xFFFF) & ~0xFFFF)
        mu.mem_write(0x400000, bytes(img))
        self.exe_end = 0x400000 + len(img)
        for m in modules:
            base = BASES[m]
            img, exports, imports = _image(m, lambda m=m: pefile.PE(str(TEST_DLLS[m])), base)
            img = bytearray(img)
            self._redirect(img, imports, base)
            mu.mem_map(base, (len(img) + 0xFFFF) & ~0xFFFF)
            mu.mem_write(base, bytes(img))
            self.exports[m] = exports
        mu.mem_map(STACK_TOP - 0x40000, 0x40000)
        mu.mem_map(HALT, 0x1000)
        mu.mem_write(HALT, b"\xF4")
        for region, size in ((VILLAGE, 0x1000000), (STATE, 0x100000), (OBJ, 0x10000),
                             (RECORD, 0x10000), (STRINGS, 0x10000)):
            mu.mem_map(region, size)
        self.leaves: dict[int, Leaf] = {}
        self.real: set[int] = set()          # exe routines that run for real
        self.real_ranges: list[tuple[int, int]] = []   # patcher-appended code that runs for real
        self.watch: set[int] = set()
        self.poke: dict[int, dict] = {}      # at this address, set these registers
        self.seen: list[int] = []
        self.calls: list[tuple] = []
        self.stop_at: int | None = None
        self.error: str | None = None
        mu.hook_add(UC_HOOK_CODE, self._hook)

    # -- imports -------------------------------------------------------------
    def _redirect(self, img: bytearray, imports, base: int) -> None:
        for name, iat in imports:
            stub = self._next_stub
            self._next_stub += 16
            self.import_stub[stub] = name
            struct.pack_into("<I", img, iat - base, stub)
            n = STDCALL_BYTES.get(name)
            code = (b"\xC2" + struct.pack("<H", n)) if n is not None else b"\xF4"
            self.mu.mem_write(stub, code)

    def _module_by_name(self, text: str):
        base_name = text.replace("/", "\\").split("\\")[-1].lower()
        for m, f in MODULE_FILE.items():
            if f.lower() == base_name and m in self.loaded and m in self.exports:
                return m
        return None

    def _import(self, name: str) -> None:
        mu = self.mu
        sp = mu.reg_read(UC_X86_REG_ESP)
        arg = lambda k: struct.unpack("<I", mu.mem_read(sp + 4 + 4 * k, 4))[0]
        cstr = lambda va: bytes(mu.mem_read(va, 260)).split(b"\0")[0].decode("latin-1")
        if name in ("GetModuleHandleA", "LoadLibraryA"):
            m = self._module_by_name(cstr(arg(0)))
            mu.reg_write(UC_X86_REG_EAX, BASES[m] if m else 0)
            self.calls.append((name, cstr(arg(0))))
        elif name == "GetProcAddress":
            module = next((m for m, b in BASES.items() if b == arg(0)), None)
            proc = cstr(arg(1))
            mu.reg_write(UC_X86_REG_EAX, self.exports.get(module, {}).get(proc, 0))
            self.calls.append((name, proc))
        elif name == "GetModuleFileNameA":
            path = b"C:\\Games\\VV\\game.exe\0"
            mu.mem_write(arg(1), path)
            mu.reg_write(UC_X86_REG_EAX, len(path) - 1)
        elif name == "lstrcpyA":
            text = bytes(mu.mem_read(arg(1), 260)).split(b"\0")[0] + b"\0"
            mu.mem_write(arg(0), text)
            mu.reg_write(UC_X86_REG_EAX, arg(0))
        elif name == "VirtualQuery":
            # Committed, execute-read: what the executable's code pages are.
            mu.mem_write(arg(1), struct.pack("<7I", arg(0) & ~0xFFF, 0x400000, 0x20, 0x1000,
                                             0x1000, 0x20, 0x1000000))
            mu.reg_write(UC_X86_REG_EAX, 28)
        elif name == "VirtualProtect":
            mu.mem_write(arg(3), struct.pack("<I", 0x20))
            mu.reg_write(UC_X86_REG_EAX, 1)
        elif name == "FlushInstructionCache":
            mu.reg_write(UC_X86_REG_EAX, 1)
        elif name == "GetCurrentProcess":
            mu.reg_write(UC_X86_REG_EAX, 0xFFFFFFFF)
        else:
            self.error = f"unexpected import {name}"
            mu.emu_stop()

    # -- running ---------------------------------------------------------------
    def _hook(self, mu, address, size, user_data):
        if address == self.stop_at:
            mu.emu_stop()
            return
        if address in self.watch:
            self.seen.append(address)
        poke = self.poke.get(address)
        if poke is not None:
            for reg, value in poke.items():
                mu.reg_write(reg, value)
        name = self.import_stub.get(address)
        if name is not None:
            self._import(name)
            return
        leaf = self.leaves.get(address)
        if leaf is not None:
            sp = mu.reg_read(UC_X86_REG_ESP)
            ret, *args = struct.unpack(f"<{1 + leaf.nargs}I", mu.mem_read(sp, 4 * (1 + leaf.nargs)))
            ecx = mu.reg_read(UC_X86_REG_ECX)
            # An argument that points into the stack is recorded as what it
            # points at: the wrapper runs the scheduler a few bytes deeper.
            # (An output pointer is recorded as just "stack".)
            shown = tuple((("stack",) if leaf.out else ("stack", self.u32(a)))
                          if STACK_TOP - 0x40000 <= a < STACK_TOP else a for a in args)
            value = leaf.fn(self, args, ecx, ret)
            self.calls.append((leaf.name or hex(address), shown, ecx))
            mu.reg_write(UC_X86_REG_EAX, (value or 0) & 0xFFFFFFFF)
            mu.reg_write(UC_X86_REG_ESP, sp + 4 + (0 if leaf.cdecl else 4 * leaf.nargs))
            mu.reg_write(UC_X86_REG_EIP, ret)
            return
        if 0x400000 <= address < self.exe_end:
            code = bytes(mu.mem_read(address, 5))
            if code[0] == 0xE8:
                target = (address + 5 + struct.unpack("<i", code[1:5])[0]) & 0xFFFFFFFF
                if (target not in self.leaves and target not in self.real and 0x400000 <= target < self.exe_end
                        and not any(lo <= target < hi for lo, hi in self.real_ranges)):
                    self.error = f"unscripted call to {target:#x} from {address:#x}"
                    mu.emu_stop()

    def call_export(self, module: str, name: str, *args: int, stdcall: bool = True) -> int:
        mu = self.mu
        esp = STACK_TOP - 0x30000
        mu.mem_write(esp, struct.pack(f"<{1 + len(args)}I", HALT, *args))
        mu.reg_write(UC_X86_REG_ESP, esp)
        saved, self.stop_at = self.stop_at, HALT
        mu.emu_start(self.exports[module][name], HALT, count=200000)
        self.stop_at = saved
        return mu.reg_read(UC_X86_REG_EAX)

    def plan(self, start: int, stop: int, regs: dict, stack: tuple[int, ...] = (), reset=None) -> None:
        """The caller this machine's decisions start from (see decide)."""
        self._plan = (start, stop, dict(regs), tuple(stack))
        self._reset = reset

    def decide(self) -> "Machine":
        """One decision from the planned caller; the calls and sites of this
        decision only.  The companions' state (their generators, the last
        decision) carries over, as it does in a running game."""
        self.calls, self.seen = [], []
        if self._reset is not None:
            self._reset(self)
        start, stop, regs, stack = self._plan
        self.run(start, stop, regs, stack)
        return self

    # Each companion's test-build roll record (force, draws): the shared roll
    # in fix-huts, the own-roll fallbacks in the other two.
    ROLL_RECORDS = {"fix_huts": "VvfpFixHutsRollTest", "work_first": "VvfpWorkFirstRollTest",
                    "healers": "VvfpHealersStudyRollTest"}

    def roll_force(self, force: int) -> None:
        for module, name in self.ROLL_RECORDS.items():
            if module in self.exports:
                self.mu.mem_write(self.exports[module][name], struct.pack("<ii", force, 0))

    def draws(self, module: str = "fix_huts") -> int:
        return struct.unpack("<ii", self.mu.mem_read(self.exports[module][self.ROLL_RECORDS[module]], 8))[1]

    def seed(self, seed: int) -> None:
        self.call_export("fix_huts", "VvfpFixHutsProbeSeedRoll", seed)

    def run(self, start: int, stop: int, regs: dict, stack: tuple[int, ...] = (), count: int = 3_000_000):
        mu = self.mu
        esp = STACK_TOP - 0x1000 - 4 * len(stack)
        if stack:
            mu.mem_write(esp, struct.pack(f"<{len(stack)}I", *stack))
        mu.reg_write(UC_X86_REG_ESP, esp)
        for reg, value in regs.items():
            mu.reg_write(reg, value)
        self.stop_at, self.error = stop, None
        self.esp0 = esp
        try:
            mu.emu_start(start, 0, count=count)
        except UcError as exc:
            eip = mu.reg_read(UC_X86_REG_EIP)
            raise AssertionError(f"emulation fault {exc} at {eip:#x}") from None
        if self.error:
            raise UnscriptedCall(self.error)
        if mu.reg_read(UC_X86_REG_EIP) != stop:
            raise AssertionError(f"stopped at {mu.reg_read(UC_X86_REG_EIP):#x}, not {stop:#x}")
        self.stop_at = None

    def install_runtime(self) -> int:
        """What the per-frame companions do: VvfpFixHutsInstall(game) (which
        loads and installs Work First through its bridge) and, in A New Home
        and The Lost Children, VvfpHealersStudyInstall(game).  Returns the
        fix-huts install's answer."""
        no = GAME_NO[self.game]
        result = self.call_export("fix_huts", "VvfpFixHutsInstall", no) if "fix_huts" in self.exports else 0
        if "healers" in self.exports and no in (1, 2):
            self.call_export("healers", "VvfpHealersStudyInstall", no)
        return result

    def u32(self, va: int) -> int:
        return struct.unpack("<I", self.mu.mem_read(va, 4))[0]

    def w32(self, va: int, value: int) -> None:
        self.mu.mem_write(va, struct.pack("<i" if value < 0 else "<I", value))

    def w8(self, va: int, value: int) -> None:
        self.mu.mem_write(va, bytes([value & 0xFF]))


def high(n: int) -> int:
    return max(0, n - 1)


class Rolls:
    """The game's rand(n): by the call's return address, else `default`."""

    def __init__(self, by_site=None, default=high):
        self.by_site = dict(by_site or {})
        self.default = default
        self.seen: list[tuple[int, int, int]] = []

    def __call__(self, m, args, ecx, ret):
        n = max(1, args[0])
        value = self.by_site.get(ret)
        value = self.default(n) if value is None else (value(n) if callable(value) else value)
        self.seen.append((ret, n, value))
        return value


def starts(m: Machine, names) -> list[tuple]:
    return [c for c in m.calls if c[0] in names]


# ---- A New Home -------------------------------------------------------------
V1 = dict(caller=0x4487C8, back=0x4487CD, sched=0x448220, disp=0x4472C0,
          food_site=0x448336, low=0x448342, high=0x44836F, hut_site=0x447724, level_site=0x44765E,
          done=0x44843D, gate_roll=0x448263, first_roll=0x4474B1, skip_roll=0x44772B,
          level2_roll=0x4475E7)
# Builder Action Fixes' cave (data/builds.json) and the instruction after its rdtsc.
BAF_CAVE = 0x4568A0
BAF_AFTER_RDTSC = BAF_CAVE + 38
V1_STARTS = {0x442090: "build hut", 0x444690: "project 3", 0x43FDA0: "project 2", 0x43FC20: "project 4",
             0x444380: "project 8", 0x442A60: "project 7", 0x440940: "project 5", 0x446600: "examine",
             0x447CD0: "continue", 0x446030: "fallback", 0x443270: "study cactus"}


def new_home(*, rows, runtime=True, force=FORCE_PASS, food=100, pref=4, level=3, huts=(1, 0, 0),
             projects=None, population=10, activity=0, rolls=None, general_job=0, cont=0,
             modules=("fix_huts", "work_first", "healers"), loaded=None, seed=None,
             preferred_pick=None, rdtsc=None) -> Machine:
    """One run of A New Home's idle scheduler from its per-frame caller
    (0x4487C8: `call 0x448220`), for villager INDEX.  rows: the patcher rows
    the executable is rendered with (() = stock); runtime: install the
    companions as their per-frame callers do."""
    m = Machine("vv1", rendered("vv1", tuple(rows)), modules=modules if runtime else (), loaded=loaded)
    record = VILLAGE + INDEX * 0x3D8
    m.w32(VILLAGE + 0x3E010, STATE)
    m.w32(VILLAGE + 0x3E02C, STRINGS)
    m.mu.mem_write(STRINGS, b"Nothing\0")
    m.w32(record + 0x348, 0x200)                 # an adult (the child routine starts below 0x118)
    m.w32(record + 0x3D0, pref)                  # the selected job: 4 Building, 5 Healing
    m.w32(record + 0x3B8, activity)              # the last activity (9: plant study)
    m.w32(STATE + 0xA2EC, food)
    m.w32(STATE + 0xA2CC, level)
    for i, done in zip((9, 10, 11), huts):
        m.w8(STATE + 0x9F9C + 8 * i + 4, done)
    for pid, (progress, done) in (projects or {}).items():
        m.w32(STATE + 0x9F9C + 8 * pid, progress)
        m.w8(STATE + 0x9F9C + 8 * pid + 4, done)
    rolls = rolls or Rolls()
    m.rand = rolls
    m.leaves.update({
        0x402F10: Leaf(1, rolls, cdecl=True, name="rand"),
        0x433970: Leaf(1, lambda m, a, c, r: STRINGS, name="string"),
        0x44B23D: Leaf(2, lambda m, a, c, r: a[0], cdecl=True, name="strcpy"),
        0x439AE0: Leaf(2, lambda m, a, c, r: (pref if preferred_pick is None else preferred_pick)
                       if a[1] == 1 else general_job, name="picker"),
        0x41CF90: Leaf(0, lambda m, a, c, r: population, name="population"),
        0x43B520: Leaf(2, lambda m, a, c, r: 100, name="0x43B520"),
    })
    for va, name in V1_STARTS.items():
        nargs = {0x442090: 3, 0x442A60: 2, 0x446600: 2, 0x447CD0: 2}.get(va, 1)
        result = cont if va == 0x447CD0 else 1
        m.leaves[va] = Leaf(nargs, lambda m, a, c, r, result=result: result, name=name)
    m.real.update({V1["sched"], V1["disp"]})
    m.watch.update({V1["food_site"], V1["hut_site"], V1["level_site"], V1["high"], V1["low"], V1["disp"],
                    BAF_CAVE})
    if rdtsc is not None:
        m.poke[BAF_AFTER_RDTSC] = {UC_X86_REG_EAX: rdtsc, UC_X86_REG_EDX: 0}
    if runtime:
        m.install_runtime()
        m.roll_force(force)
        if seed is not None:
            m.seed(seed)
    m.plan(V1["caller"], V1["back"], {UC_X86_REG_ECX: VILLAGE}, stack=(INDEX,))
    return m.decide()


def v1_outcome(m: Machine):
    s = [c for c in m.calls if c[0] in V1_STARTS.values()]
    return [(c[0],) + ((c[1][1],) if c[0] in ("build hut", "examine") else ()) for c in s]


def leaf_calls(m: Machine) -> list[tuple]:
    """Every scripted game routine the run called, in order, with its
    arguments -- what the executable asked the game to do."""
    return [c for c in m.calls if c[0] not in STDCALL_BYTES]


# Scripted routines that only answer a question (is this hut complete, what
# is the population, does the villager dislike ...): the companions ask some
# of them before deciding whether to act at all, which changes nothing in
# the game.  Everything else -- every random number drawn and every routine
# that starts, continues or copies something -- must match the stock run.
QUERIES = {"done", "state", "pstate", "pdone", "population", "dislike", "has item", "likes", "other",
           "farm test", "0x4396D0", "0x430fd0", "0x421570", "0x4388d0", "0x4322e0"}


def effects(m: Machine) -> list[tuple]:
    return [c for c in leaf_calls(m) if c[0] not in QUERIES]


# ---- The Lost Children ------------------------------------------------------
V2 = dict(caller=0x464E9C, back=0x464EA1, sched=0x461850, disp=0x45FBF0,
          food_site=0x4619E9, low=0x4619F5, high=0x461A22, hut_site=0x46029D, level_site=0x4601F2,
          done=0x461AF0, gate_roll=0x461893)
V2_STARTS = {0x457130: "build", 0x45F7C0: "examine", 0x44AB90: "project 1", 0x45FBE0: "project 17",
             0x45BA20: "project 8", 0x45A000: "project 12", 0x45F410: "project 11",
             0x460590: "continue", 0x460B20: "fallback"}


def lost_children(*, rows, runtime=True, force=FORCE_PASS, food=100, pref=5, level=3,
                  huts=((24, 1), (0, 0), (0, 0)), projects=None, population=10, task=0, ea74=3, ea8c=3,
                  rolls=None, general_job=0, cont=0, modules=("fix_huts", "work_first", "healers"),
                  loaded=None, seed=None, preferred_pick=None) -> Machine:
    """One run of The Lost Children's idle scheduler from its per-frame caller
    (0x464E9C: `call 0x461850`), for villager INDEX.  huts: (progress,
    complete) for 24/25/26; projects: {id: (progress, complete)}, every other
    project complete."""
    m = Machine("vv2", rendered("vv2", tuple(rows)), modules=modules if runtime else (), loaded=loaded)
    record = VILLAGE + INDEX * 0xE48C
    m.w32(VILLAGE + 0xE574D4, STATE)
    m.w32(VILLAGE + 0xE574F0, STRINGS)
    m.mu.mem_write(STRINGS, b"Nothing\0")
    m.w32(record + 0x530, 0x200)                 # an adult
    m.w32(record + 0x7F8, pref)                  # the selected job: 5 Building, 3 Healing
    m.w32(record + 0x7E0, task)                  # the task / state (9: plant study)
    m.w32(STATE + 0x2EAA4, food)
    m.w32(STATE + 0x2EA84, level)
    m.w32(STATE + 0x2EA74, ea74)
    m.w32(STATE + 0x2EA8C, ea8c)
    projects = dict(projects or {})
    for pid in range(1, 32):
        progress, done = projects.get(pid, (0, 1))
        if pid in (24, 25, 26):
            progress, done = huts[pid - 24]
        m.w32(STATE + 0x2E754 + 8 * pid, progress)
        m.w8(STATE + 0x2E758 + 8 * pid, done)
    rolls = rolls or Rolls()
    m.rand = rolls
    m.leaves.update({
        0x4031A0: Leaf(1, rolls, cdecl=True, name="rand"),
        0x441680: Leaf(1, lambda m, a, c, r: STRINGS, name="string"),
        0x4682BD: Leaf(2, lambda m, a, c, r: a[0], cdecl=True, name="strcpy"),
        0x44B400: Leaf(0, lambda m, a, c, r: 0xFFFFFFFF, name="0x44B400"),
        0x461580: Leaf(1, lambda m, a, c, r: 0, name="0x461580"),
        0x449C60: Leaf(2, lambda m, a, c, r: (pref if preferred_pick is None else preferred_pick)
                       if a[1] == 1 else general_job, name="picker"),
        0x425860: Leaf(0, lambda m, a, c, r: population, name="population"),
        0x44B4D0: Leaf(2, lambda m, a, c, r: 100, name="0x44B4D0"),
    })
    for va, name in V2_STARTS.items():
        nargs = {0x457130: 3, 0x45F7C0: 2, 0x460590: 2}.get(va, 1)
        result = cont if va == 0x460590 else 1
        m.leaves[va] = Leaf(nargs, lambda m, a, c, r, result=result: result, name=name)
    m.real.update({V2["sched"], V2["disp"]})
    m.watch.update({V2["food_site"], V2["hut_site"], V2["level_site"], V2["high"], V2["low"], V2["disp"]})
    if runtime:
        m.install_runtime()
        m.roll_force(force)
        if seed is not None:
            m.seed(seed)
    m.plan(V2["caller"], V2["back"], {UC_X86_REG_ECX: VILLAGE}, stack=(INDEX,))
    return m.decide()


def v2_outcome(m: Machine):
    s = [c for c in m.calls if c[0] in V2_STARTS.values()]
    return [(c[0],) + ((c[1][1],) if c[0] in ("build", "examine") else ()) for c in s]


# ---- The Tree of Life / New Believers ------------------------------------------
LATER = {
    "vv4": dict(loop=0x465B13, back=0x465B27, sched=0x465840, disp=0x4639B0, food=0x4D6DD0,
                food_site=0x4659B0, filter_site=0x463F8A, state=0x438980, done=0x438960, obj=0x4D8BF8,
                dislike=0x45D1F0, rand=0x4036D0, start=0x45DEC0, rec_dislikes=0x1E6C, fix_job=0x2E,
                build_job=8, open_at=1, pick=0x461CC0, pref=0x1C70, farm_test=0x4618F0,
                string_obj=0x44DA20, string=0x44D3D0, strncpy=0x4724E0, name_flag=0x1CC6,
                gate_roll=0x465886, other=(0x466CE0,), skill=0x46AC20, fallback=0x461EE0,
                counts={0x430FD0: 0, 0x421570: 500}, food_job=0x41, dispatch_high=0x465A2A,
                dispatch_low=0x465A17, farm_call=0x4659D2),
    "vv5": dict(loop=0x46F3D3, back=0x46F3E7, sched=0x46F070, disp=0x46C540, food=0x51D34C,
                food_site=0x46F271, filter_site=0x46CADA, state=0x43AEA0, done=0x43AE80, obj=0x51E008,
                dislike=0x464F90, rand=0x403660, start=0x465580, rec_dislikes=0x1F68, fix_job=0x35,
                build_job=0x10, open_at=2, pick=0x46A3C0, pref=0x1C74, farm_test=0x469D70,
                string_obj=0x450D40, string=0x4506D0, strncpy=0x47D7C0, name_flag=0x1CD6,
                gate_roll=0x46F0D6, other=(0x477040,), skill=0x4755C0, fallback=0x46A610,
                counts={0x4388D0: 0, 0x4322E0: 0}, food_job=0x47, dispatch_high=0x46F2EA,
                dispatch_low=0x46F2D6, farm_call=0x46F291),
}


def later(game: str, *, rows, runtime=True, force=FORCE_PASS, food=100, pref=4, pick=4, built=(19,),
          open_=(), dislikes=False, rolls=None, modules=("fix_huts", "work_first"), loaded=None,
          seed=None, farming_first=False, option6=False) -> Machine:
    """One decision of The Tree of Life / New Believers: their own retry loop
    (0x465B13 / 0x46F3D3: up to ten runs of the idle scheduler while the
    villager has no job) for the villager object OBJ.  built: complete
    projects (huts 19-22 and others); open_: projects the game offers
    (state test passes, not complete)."""
    g = LATER[game]
    m = Machine(game, rendered(game, tuple(rows)), modules=modules if runtime else (), loaded=loaded)
    m.w32(OBJ + 0x1B88, RECORD)
    m.w32(RECORD + g["pref"], pref)
    m.w32(RECORD + 0x1B8C, 0x200)                # an adult
    m.w32(g["food"], food)
    m.mu.mem_write(STRINGS, b"Nothing\0")
    rolls = rolls or Rolls()
    m.rand = rolls

    def state(m, a, c, r):
        return g["open_at"] if a[0] in open_ else 0

    def done(m, a, c, r):
        if game == "vv5" and a[0] == 14:
            return 1                   # VV5 option 7 (project 14) off
        return 1 if a[0] in built else 0

    def start(m, a, c, r):
        m.w32(OBJ, 1)                  # the villager has a job: the retry loop ends
        return 1

    def skill(m, a, c, r):
        m.w32(a[0], 100)
        return a[0]

    m.leaves.update({
        g["state"]: Leaf(1, state, name="state"),
        g["done"]: Leaf(1, done, name="done"),
        g["dislike"]: Leaf(1, lambda m, a, c, r: 1 if dislikes and a[0] in (0x1E, 0x35) else 0, name="dislike"),
        g["rand"]: Leaf(1, rolls, cdecl=True, name="rand"),
        g["start"]: Leaf(2, start, name="start"),
        g["pick"]: Leaf(0, lambda m, a, c, r: pick, name="picker"),
        g["farm_test"]: Leaf(1, lambda m, a, c, r: 1 if farming_first else 0, name="farm test"),
        g["string_obj"]: Leaf(1, lambda m, a, c, r: STRINGS + 0x100, name="string table"),
        g["string"]: Leaf(0, lambda m, a, c, r: STRINGS, name="string"),
        g["strncpy"]: Leaf(3, lambda m, a, c, r: a[0], cdecl=True, name="strncpy"),
    })
    for va in g["other"]:
        m.leaves[va] = Leaf(0, lambda m, a, c, r: 0xFFFFFFFF if game == "vv4" else 0, name=hex(va))
    counts = dict(g["counts"])
    if option6 and game == "vv5":
        counts[0x4388D0] = 50                    # 0 < count < 100: option 6 on offer
    for va, value in counts.items():
        m.leaves[va] = Leaf(0, lambda m, a, c, r, value=value: value, name=hex(va))
    if game == "vv4":
        # Option 6/7's counts: 0x4396D0(0x4D86A8) = 5 keeps option 6 off (1
        # with option6, and 0x421570 below 100); 0x4396D0(0x4D8720) = 1 keeps
        # option 7 off.
        m.leaves[0x4396D0] = Leaf(0, lambda m, a, c, r: (1 if option6 else 5) if c == 0x4D86A8 else 1,
                                  name="0x4396D0")
        if option6:
            m.leaves[0x421570] = Leaf(0, lambda m, a, c, r: 50, name="0x421570")
    else:
        # Dispatcher case 3's flag object: its byte +0x17E10 clear.
        m.leaves[0x425950] = Leaf(0, lambda m, a, c, r: VILLAGE, name="flags")
    m.leaves[g["skill"]] = Leaf(1, skill, name="skill", out=True)
    m.leaves[g["fallback"]] = Leaf(0, lambda m, a, c, r: 1, name="fallback")
    m.real.update({g["sched"], g["disp"], 0x465B00 if game == "vv4" else 0x46F3C0})
    m.watch.update({g["food_site"], g["filter_site"], g["disp"], g["sched"]})
    if runtime:
        m.install_runtime()
        m.roll_force(force)
        if seed is not None:
            m.seed(seed)
    m.plan(g["loop"], g["back"], {UC_X86_REG_ESI: OBJ, UC_X86_REG_EDI: 0},
           reset=lambda m: m.w32(OBJ, 0))           # no job yet
    return m.decide()


def later_outcome(game: str, m: Machine):
    g = LATER[game]
    out = []
    for name, args, ecx in leaf_calls(m):
        if name != "start":
            continue
        job, arg = args
        value = arg[1] if isinstance(arg, tuple) else struct.unpack("<i", m.mu.mem_read(arg, 4))[0]
        value = value - (1 << 32) if value >= 1 << 31 else value
        out.append(("fix", value) if job == g["fix_job"] else ("build", value) if job == g["build_job"]
                   else ("job", job))
    return out


# ---- The Secret City ----------------------------------------------------------
V3 = dict(loop=0x45C380, back=0x45C394, sched=0x45BFE0, disp=0x45AF00, food=0x582490,
          state=0x432210, done=0x4321F0, pstate=0x4358F0, pdone=0x4358D0, rand=0x4032D0, start=0x455570,
          likes=0x4547B0, other=0x45EF30, pick=0x459730, food_site=0x45C229, filter_site=0x45B39E)


def secret_city(*, rows, runtime=True, force=FORCE_PASS, food=100, pref=4, pick=4, huts_built=(0,),
                huts_open=(), projects_open=(), farming_skill=10, rolls=None,
                modules=("fix_huts", "work_first"), loaded=None, seed=None) -> Machine:
    """One decision of The Secret City: its own retry loop (0x45C380: up to
    ten runs of the idle scheduler while the villager has no job) for the
    villager record RECORD (the scheduler's `this` and argument alike)."""
    m = Machine("vv3", rendered("vv3", tuple(rows)), modules=modules, loaded=loaded)
    m.w32(RECORD + 0xEC0, pref)
    m.w32(RECORD + 0xDC4, 0x200)                 # an adult
    m.w32(RECORD + 0xEAC, farming_skill)
    m.w32(V3["food"], food)
    m.mu.mem_write(STRINGS, b"Nothing\0")
    rolls = rolls or Rolls()
    m.rand = rolls

    def start(m, a, c, r):
        m.w32(RECORD, 1)               # the villager has a job: the retry loop ends
        return 1

    def skill(m, a, c, r):
        m.w32(a[0], 100)
        return a[0]

    m.leaves.update({
        V3["state"]: Leaf(1, lambda m, a, c, r: 2 if a[0] in huts_open else 0, name="state"),
        V3["done"]: Leaf(1, lambda m, a, c, r: 1 if a[0] in huts_built else 0, name="done"),
        V3["pstate"]: Leaf(1, lambda m, a, c, r: 2 if a[0] in projects_open else 0, name="pstate"),
        V3["pdone"]: Leaf(1, lambda m, a, c, r: 0, name="pdone"),
        V3["rand"]: Leaf(1, rolls, cdecl=True, name="rand"),
        V3["start"]: Leaf(2, start, name="start"),
        V3["likes"]: Leaf(1, lambda m, a, c, r: 0, name="likes"),
        V3["other"]: Leaf(0, lambda m, a, c, r: 0, name="other"),
        V3["pick"]: Leaf(1, lambda m, a, c, r: pick, name="picker"),
        0x42F740: Leaf(1, lambda m, a, c, r: STRINGS + 0x100, name="string table"),
        0x42F190: Leaf(0, lambda m, a, c, r: STRINGS, name="string"),
        0x46F780: Leaf(3, lambda m, a, c, r: a[0], cdecl=True, name="strncpy"),
        0x455E10: Leaf(2, lambda m, a, c, r: 0, name="has item"),
        0x45C950: Leaf(0, lambda m, a, c, r: 0xFFFFFFFF, name="0x45C950"),
        0x462460: Leaf(1, skill, name="skill", out=True),
        0x4598D0: Leaf(1, lambda m, a, c, r: 1, name="fallback"),
    })
    m.real.update({V3["sched"], V3["disp"], 0x45C360})
    m.real_ranges.append((0x6DF000, 0x6E1000))    # the row's stubs in the page Origins appends
    m.watch.update({V3["food_site"], V3["filter_site"], V3["disp"], V3["sched"]})
    m.roll_force(force) if "fix_huts" in modules else None
    if seed is not None:
        m.seed(seed)
    m.plan(V3["loop"], V3["back"], {UC_X86_REG_ESI: RECORD, UC_X86_REG_EDI: RECORD, UC_X86_REG_EBX: 0},
           reset=lambda m: m.w32(RECORD, 0))        # no job yet
    return m.decide()


def v3_outcome(m: Machine):
    out = []
    for name, args, ecx in leaf_calls(m):
        if name != "start":
            continue
        job, arg = args
        value = arg[1] if isinstance(arg, tuple) else struct.unpack("<i", m.mu.mem_read(arg, 4))[0]
        value = value - (1 << 32) if value >= 1 << 31 else value
        out.append(("fix", value) if job == 0x56 else ("build", value) if job == 9 else ("job", job))
    return out


# ---- The scenarios ------------------------------------------------------------
GAMES = ("vv1", "vv2", "vv3", "vv4", "vv5")
STOCK_PRESENT = all(p.is_file() for p in STOCK.values())
STOCK_ABSENT = "the stock executables (research/stock-executables) are gitignored and absent"
ROWS = {g: tuple(_rows(g, False)) for g in GAMES}
ROWS_BAF = tuple(_rows("vv1", True))
WORLD = {"vv1": new_home, "vv2": lost_children, "vv3": secret_city,
         "vv4": lambda **k: later("vv4", **k), "vv5": lambda **k: later("vv5", **k)}
OUTCOME = {"vv1": v1_outcome, "vv2": v2_outcome, "vv3": v3_outcome,
           "vv4": lambda m: later_outcome("vv4", m), "vv5": lambda m: later_outcome("vv5", m)}


def _low(game):
    """Every stock construction roll says "not this time" (the scheduler's own
    65% gate still lets the villager through)."""
    gate = {"vv1": V1["gate_roll"], "vv2": V2["gate_roll"]}[game]
    return Rolls({gate: 99}, default=lambda n: 0)


# (name, the state, what the patches do when the roll passes, the patched
# sites that decision must reach).  When the roll fails, every one of them
# must do exactly what the stock executable does with the same state.
SCENARIOS = {
    "vv1": [
        ("idle hut fix", dict(huts=(1, 0, 0)), [("examine", 9)], {V1["hut_site"], V1["level_site"]}),
        ("option A at the skip roll", dict(huts=(1, 0, 0), population=23, rolls=lambda: Rolls(
            {V1["gate_roll"]: 99, V1["first_roll"]: 0})), [("build hut", 10)], {V1["hut_site"]}),
        ("option A at the level gate", dict(huts=(1, 0, 0), population=23, level=2, rolls=lambda: Rolls(
            {V1["gate_roll"]: 99, V1["first_roll"]: 0})), [("build hut", 10)], {V1["level_site"]}),
        ("below level 3, every hut built", dict(huts=(1, 1, 1), level=2), [("examine", 11)], {V1["level_site"]}),
        ("food bypass", dict(huts=(1, 0, 0), food=500), [("examine", 9)], {V1["food_site"], V1["low"]}),
        ("healer keeps studying", dict(pref=5, activity=9, food=500, cont=1), [("continue",)], {V1["high"]}),
        ("work first", dict(preferred_pick=0, huts=(1, 0, 0), population=23), [("build hut", 10)],
         {V1["disp"]}),
    ],
    "vv2": [
        ("idle hut fix", dict(), [("examine", 24)], {V2["hut_site"], V2["level_site"]}),
        ("option A at the skip roll", dict(huts=((24, 1), (2, 0), (0, 0)), population=30, rolls=lambda: _low("vv2")),
         [("build", 25)], {V2["hut_site"]}),
        ("option A at the level gate", dict(huts=((24, 1), (2, 0), (0, 0)), population=30, level=1,
                                            rolls=lambda: _low("vv2")), [("build", 25)], {V2["level_site"]}),
        ("option A: the villager's own build task", dict(huts=((24, 1), (700, 1), (11, 1)), projects={7: (40, 0)},
                                                         task=15, rolls=lambda: _low("vv2")),
         [("build", 7)], {V2["hut_site"]}),
        ("below level 3, every hut built", dict(huts=((24, 1), (700, 1), (11, 1)), level=2), [("examine", 26)],
         {V2["level_site"]}),
        ("food bypass", dict(food=500), [("examine", 24)], {V2["food_site"], V2["low"]}),
        ("healer keeps studying", dict(pref=3, task=9, food=500, cont=1), [("continue",)], {V2["high"]}),
        ("work first", dict(preferred_pick=0, huts=((24, 1), (2, 0), (0, 0)), population=30), [("build", 25)],
         {V2["disp"]}),
    ],
    "vv3": [
        ("idle hut fix and food bypass", dict(huts_built=(0,)), [("fix", 0)], {V3["food_site"], V3["filter_site"]}),
        ("construction before the stock fix", dict(huts_built=(0, 1, 2, 3), projects_open=(6,), food=500),
         [("job", 0x7F)], {V3["filter_site"]}),
        ("work first", dict(pick=3, huts_built=(0,), food=500), [("fix", 0)], {V3["disp"], V3["filter_site"]}),
    ],
}
for _g in ("vv4", "vv5"):
    SCENARIOS[_g] = [
        ("idle hut fix and food bypass", dict(built=(19,)), [("fix", 0)],
         {LATER[_g]["food_site"], LATER[_g]["filter_site"]}),
        ("option A: the dislike roll took the new hut", dict(built=(19,), open_=(20,), dislikes=True, food=500),
         [("build", 1)], {LATER[_g]["filter_site"]}),
        ("option A: it took the project, every hut built", dict(built=(19, 20, 21, 22), open_=(23,), dislikes=True,
                                                               food=500), [("build", 4)], {LATER[_g]["filter_site"]}),
        ("construction before the stock fix", dict(built=(19, 20, 21, 22), open_=(23,), food=500), [("build", 4)],
         {LATER[_g]["filter_site"]}),
        ("work first", dict(pick=3, built=(19,), food=500), [("fix", 0)], {LATER[_g]["disp"]}),
    ]


def _kw(kw: dict) -> dict:
    return {k: (v() if callable(v) and k == "rolls" else v) for k, v in kw.items()}


def run_three(game: str, kw: dict):
    """The same decision with the roll forced to pass, forced to fail, and in
    the stock executable (no rows, no companions)."""
    world = WORLD[game]
    passed = world(rows=ROWS[game], force=FORCE_PASS, **_kw(kw))
    failed = world(rows=ROWS[game], force=FORCE_FAIL, **_kw(kw))
    stock = world(rows=(), runtime=False, **_kw(kw))
    return passed, failed, stock


@unittest.skipUnless(TEST_BUILDS_PRESENT, TEST_BUILD_ABSENT)
@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
class FromTheRealCallerTests(unittest.TestCase):
    def test_every_patched_site_is_reached_and_acts_when_the_roll_passes(self):
        for game, scenarios in SCENARIOS.items():
            for name, kw, expected, sites in scenarios:
                with self.subTest(game=game, scenario=name):
                    passed, failed, stock = run_three(game, kw)
                    self.assertEqual(OUTCOME[game](passed), expected)
                    self.assertTrue(sites <= set(passed.seen),
                                    f"not reached: {[hex(s) for s in sites - set(passed.seen)]}")
                    self.assertNotEqual(OUTCOME[game](passed), OUTCOME[game](stock),
                                        "the site must change something here, or it proves nothing")
                    self.assertEqual(passed.draws(), 1, "one roll for the decision")

    def test_when_the_roll_fails_the_decision_is_exactly_the_stock_one(self):
        # Every random number the game draws and every routine that starts,
        # continues or copies something -- in order, with its arguments -- is
        # what the unpatched executable does with the same state.
        for game, scenarios in SCENARIOS.items():
            for name, kw, expected, sites in scenarios:
                with self.subTest(game=game, scenario=name):
                    passed, failed, stock = run_three(game, kw)
                    self.assertEqual(effects(failed), effects(stock))
                    self.assertEqual(OUTCOME[game](failed), OUTCOME[game](stock))
                    self.assertEqual(failed.draws(), 1)

    def test_option_a_goes_straight_into_construction_the_stock_roll_skipped(self):
        for game in ("vv1", "vv2", "vv4", "vv5"):
            for name, kw, expected, sites in SCENARIOS[game]:
                if not name.startswith("option A"):
                    continue
                with self.subTest(game=game, scenario=name):
                    passed, failed, stock = run_three(game, kw)
                    self.assertTrue(expected and expected[0][0] in ("build", "build hut"), expected)
                    self.assertEqual(OUTCOME[game](passed), expected)
                    self.assertNotIn(expected[0], OUTCOME[game](stock), "stock skipped it this time")
                    self.assertFalse([o for o in OUTCOME[game](passed) if o[0] in ("fix", "examine")],
                                     "never a hut fix while there is construction")

    def test_option_a_enters_every_construction_the_stock_rolls_can_skip(self):
        # Each construction entry option A jumps to (or puts back in the list)
        # is reached and starts its construction, from the real caller.
        # A New Home: every started project the level-3 branch can skip by its
        # own roll (the rolls all say "not this time"; hut 9's section and
        # project 3 have no roll of their own there).
        # Project 3 has no roll, but the stock path past the hut section
        # (first roll above 20) never tests it: the other way it is skipped.
        v1_start = {3: "project 3", 2: "project 2", 4: "project 4", 8: "project 8", 7: "project 7",
                    5: "project 5"}
        for pid, start in v1_start.items():
            with self.subTest(game="vv1", project=pid):
                first = 99 if pid == 3 else 0
                kw = dict(huts=(1, 1, 1), projects={pid: (5, 0)},
                          rolls=lambda first=first: Rolls({V1["gate_roll"]: 99, V1["first_roll"]: first},
                                                          default=lambda n: 0))
                passed, failed, stock = run_three("vv1", kw)
                self.assertEqual(v1_outcome(passed), [(start,)])
                self.assertNotIn((start,), v1_outcome(stock))
                self.assertEqual(effects(failed), effects(stock))
        # The Lost Children: the villager's own build task, every one of the
        # ten, through its jump-table handler.
        task_project = {11: 24, 12: 25, 13: 26, 14: 5, 15: 7, 16: 8, 17: 1, 18: 17, 19: 12, 20: 11}
        expected = {24: ("build", 24), 25: ("build", 25), 26: ("build", 26), 5: ("build", 5), 7: ("build", 7),
                    8: ("project 8",), 1: ("project 1",), 17: ("project 17",), 12: ("project 12",),
                    11: ("project 11",)}
        for task, pid in task_project.items():
            with self.subTest(game="vv2", task=task):
                huts = tuple((24 + i, 0) if 24 + i == pid else (24 + i, 1) for i in range(3))
                kw = dict(huts=huts, projects={pid: (40, 0)}, task=task, rolls=lambda: _low("vv2"))
                passed, failed, stock = run_three("vv2", kw)
                self.assertEqual(v2_outcome(passed), [expected[pid]])
                self.assertEqual(effects(failed), effects(stock))
        # The Tree of Life / New Believers: every construction option the
        # dislike roll removes, put back and started.
        for game in ("vv4", "vv5"):
            projects = {19: 0, 20: 1, 21: 2, 23: 4, 22: 3, 24: 5} | ({25: 6} if game == "vv4" else {})
            for pid, arg in projects.items():
                with self.subTest(game=game, project=pid):
                    built = tuple(h for h in (19, 20, 21, 22) if h != pid) if pid <= 22 else (19, 20, 21, 22)
                    kw = dict(built=built, open_=(pid,), dislikes=True, food=500)
                    passed, failed, stock = run_three(game, kw)
                    self.assertEqual(later_outcome(game, passed), [("build", arg)])
                    self.assertNotIn(("build", arg), later_outcome(game, stock), "stock skipped it")
                    self.assertEqual(effects(failed), effects(stock))
            with self.subTest(game=game, option=6):
                kw = dict(built=(19, 20, 21, 22), dislikes=True, food=500, option6=True)
                passed, failed, stock = run_three(game, kw)
                self.assertEqual(later_outcome(game, passed), [("job", 0x80 if game == "vv4" else 0x87)])
                self.assertEqual(effects(failed), effects(stock))

    def test_one_decision_draws_one_roll_however_many_patches_it_reaches(self):
        # A New Home / The Lost Children: the food bypass, Work First at the
        # dispatcher and the level gate, all in one scheduler run.
        m = new_home(rows=ROWS["vv1"], force=FORCE_PASS, preferred_pick=0, huts=(1, 0, 0), food=500, level=2)
        self.assertTrue({V1["food_site"], V1["disp"], V1["level_site"]} <= set(m.seen))
        self.assertEqual(m.draws(), 1)
        m = lost_children(rows=ROWS["vv2"], force=FORCE_PASS, preferred_pick=0, food=500, level=2,
                          huts=((24, 1), (0, 0), (0, 0)))
        self.assertTrue({V2["food_site"], V2["disp"], V2["level_site"]} <= set(m.seen))
        self.assertEqual(m.draws(), 1)
        # The Secret City: the scheduler stub, the food stub and the filter.
        m = secret_city(rows=ROWS["vv3"], force=FORCE_PASS, huts_built=(0,))
        self.assertTrue({V3["sched"], V3["food_site"], V3["filter_site"]} <= set(m.seen))
        self.assertEqual(m.draws(), 1)

    def test_the_retry_loop_is_one_decision_and_the_next_one_rolls_again(self):
        # The Tree of Life / New Believers / The Secret City run the scheduler
        # up to ten times while the villager has no job.  With the roll failed
        # and nothing to start, all ten runs are the one stock decision; the
        # next decision rolls again.
        for game in ("vv4", "vv5"):
            with self.subTest(game=game):
                g = LATER[game]
                m = later(game, rows=ROWS[game], force=FORCE_FAIL, built=(19,), open_=(20,), dislikes=True, food=500)
                self.assertEqual(m.seen.count(g["sched"]), 10, "ten scheduler runs")
                self.assertEqual(m.seen.count(g["filter_site"]), 10)
                self.assertEqual(m.draws(), 1)
                m.decide()
                self.assertEqual(m.draws(), 2, "the next decision draws its own roll")
        # The Secret City: a builder at low food whose bypass rolled and failed,
        # the stock 50% swap sending the pick on to a Building branch with
        # nothing to do: ten runs, one roll.
        m = secret_city(rows=ROWS["vv3"], force=FORCE_FAIL, huts_built=(), rolls=Rolls({0x45C24B: 0}))
        self.assertEqual(m.seen.count(V3["sched"]), 10, "ten scheduler runs")
        self.assertEqual(m.seen.count(V3["food_site"]), 10)
        self.assertEqual(m.draws(), 1)
        m.decide()
        self.assertEqual(m.draws(), 2)

    def test_healers_study_shares_the_roll_or_rolls_its_own_when_alone(self):
        cases = (("vv1", new_home, dict(pref=5, activity=9, food=500, cont=1), V1),
                 ("vv2", lost_children, dict(pref=3, task=9, food=500, cont=1), V2))
        for game, world, kw, sites in cases:
            with self.subTest(game=game, fix_huts=True):
                m = world(rows=ROWS[game], force=FORCE_PASS, **kw)
                self.assertEqual((m.draws("fix_huts"), m.draws("healers")), (1, 0), "the shared roll")
            alone = (f"{game}_enable_origins_exclusive_features", f"{game}_healers_study_regardless_of_food")
            stock = world(rows=(), runtime=False, **kw)
            for force, want in ((FORCE_PASS, [("continue",)]), (FORCE_FAIL, OUTCOME[game](stock))):
                with self.subTest(game=game, fix_huts=False, force=force):
                    m = world(rows=alone, force=force, modules=("healers",), **kw)
                    self.assertIn(sites["high"], m.seen)
                    self.assertEqual(OUTCOME[game](m), want)
                    self.assertEqual(m.draws("healers"), 1, "its own roll, once for the run")
                    if force == FORCE_FAIL:
                        self.assertEqual(effects(m), effects(stock))

    def test_about_three_in_four_decisions_are_patched(self):
        # The real generator, one running process: n decisions of a builder
        # with a hut to fix and nothing to build.  75% +- 4 standard deviations.
        n = 800
        for game in GAMES:
            with self.subTest(game=game):
                kw = _kw(SCENARIOS[game][0][1])
                m = WORLD[game](rows=ROWS[game], force=FORCE_REAL, **kw)
                expected = SCENARIOS[game][0][2]
                patched = int(OUTCOME[game](m) == expected)
                for _ in range(n - 1):
                    patched += OUTCOME[game](m.decide()) == expected
                self.assertEqual(m.draws(), n, "exactly one roll per decision")
                sd = (n * 0.75 * 0.25) ** 0.5
                self.assertLess(abs(patched - 0.75 * n), 4 * sd, f"{patched}/{n} patched")


class FixHutsDll:
    """The fix-huts test build alone (no game executable needed), to drive
    its decision bookkeeping directly through the test-build probes."""

    def __init__(self):
        img, self.ex, _ = _image("fix_huts_alone", lambda: pefile.PE(str(TEST_DLLS["fix_huts"])), BASES["fix_huts"])
        self.mu = mu = Uc(UC_ARCH_X86, UC_MODE_32)
        mu.mem_map(BASES["fix_huts"], (len(img) + 0xFFFF) & ~0xFFFF)
        mu.mem_write(BASES["fix_huts"], img)
        mu.mem_map(STACK_TOP - 0x10000, 0x10000)
        mu.mem_map(HALT, 0x1000)
        mu.mem_write(HALT, b"\xF4")

    def call(self, name: str, *args: int) -> int:
        esp = STACK_TOP - 0x1000
        self.mu.mem_write(esp, struct.pack(f"<{1 + len(args)}I", HALT, *args))
        self.mu.reg_write(UC_X86_REG_ESP, esp)
        self.mu.emu_start(self.ex[name], HALT, count=100000)
        return self.mu.reg_read(UC_X86_REG_EAX)

    def force(self, force: int) -> None:
        draws = self.draws()
        self.mu.mem_write(self.ex["VvfpFixHutsRollTest"], struct.pack("<ii", force, draws))

    def draws(self) -> int:
        return struct.unpack("<ii", self.mu.mem_read(self.ex["VvfpFixHutsRollTest"], 8))[1]

    def roll(self) -> int:
        return self.call("VvfpFixHutsRoll")

    def enter(self, game: int, ret: int, counter: int, key: int) -> None:
        self.call("VvfpFixHutsProbeEnter", game, ret, counter, key)

    def exit(self) -> None:
        self.call("VvfpFixHutsProbeExit")


LOOP_RET = {3: 0x45C38D, 4: 0x465B1F, 5: 0x46F3DF}


@unittest.skipUnless(TEST_DLLS["fix_huts"].is_file(), TEST_BUILD_ABSENT)
class DecisionBookkeepingTests(unittest.TestCase):
    """Runs without the game executables (CI): the companion's own record of
    which decision a roll belongs to."""

    def setUp(self):
        self.d = FixHutsDll()
        self.d.call("VvfpFixHutsProbeSeedRoll", 0x1234567)

    def test_a_decision_draws_once_and_keeps_its_answer(self):
        d = self.d
        d.force(FORCE_PASS)
        d.enter(1, 0x4487CD, 0, INDEX)
        self.assertEqual(d.roll(), 1)
        d.force(FORCE_FAIL)                       # a second draw would now say 0
        self.assertEqual([d.roll(), d.roll()], [1, 1])
        self.assertEqual(d.draws(), 1)
        d.exit()
        self.assertEqual(d.call("VvfpFixHutsProbeDepth"), 0)

    def test_outside_any_decision_every_ask_is_its_own_decision(self):
        d = self.d
        for _ in range(3):
            d.roll()
        self.assertEqual(d.draws(), 3)

    def test_the_retry_loop_continues_its_decision_and_nothing_else_does(self):
        for game, ret in LOOP_RET.items():
            with self.subTest(game=game):
                d = FixHutsDll()
                d.force(FORCE_PASS)
                d.enter(game, ret, 0, 0xA000)
                self.assertEqual(d.roll(), 1)
                d.exit()
                d.force(FORCE_FAIL)
                # The loop's next attempt for the same villager: the same decision.
                d.enter(game, ret, 1, 0xA000)
                self.assertEqual(d.roll(), 1)
                d.exit()
                d.enter(game, ret, 2, 0xA000)
                self.assertEqual(d.roll(), 1)
                d.exit()
                self.assertEqual(d.draws(), 1)
                # Anything else is a new decision (the forced fail shows it
                # drew): each case right after the loop's attempt 2 for 0xA000,
                # so only the one difference named separates it from attempt 3.
                for label, (g, r, counter, key) in {
                    "the loop starts again (counter 0)": (game, ret, 0, 0xA000),
                    "a counter that skips": (game, ret, 4, 0xA000),
                    "another villager": (game, ret, 3, 0xB000),
                    "another caller": (game, ret + 1, 3, 0xA000),
                }.items():
                    with self.subTest(case=label):
                        e = FixHutsDll()
                        e.force(FORCE_PASS)
                        e.enter(game, ret, 2, 0xA000)
                        e.roll()
                        e.exit()
                        e.force(FORCE_FAIL)
                        e.enter(g, r, counter, key)
                        self.assertEqual(e.roll(), 0)
                        e.exit()
                        self.assertEqual(e.draws(), 2)
                        # ...while attempt 3 itself continues it.
                        e.force(FORCE_PASS)
                        e.enter(game, ret, 2, 0xA000)
                        e.roll()
                        e.exit()
                        e.force(FORCE_FAIL)
                        e.enter(game, ret, 3, 0xA000)
                        self.assertEqual(e.roll(), 1)
                        e.exit()

    def test_a_new_home_and_the_lost_children_never_continue(self):
        # Their only retry loop does not zero its counter per villager, so a
        # continuation could not be told from the villager's next pass.
        for game, ret in ((1, 0x44848D), (2, 0x46449D)):
            with self.subTest(game=game):
                d = FixHutsDll()
                d.force(FORCE_PASS)
                d.enter(game, ret, 3, INDEX)
                d.roll()
                d.exit()
                d.force(FORCE_FAIL)
                d.enter(game, ret, 4, INDEX)
                self.assertEqual(d.roll(), 0)
                d.exit()
                self.assertEqual(d.draws(), 2)

    def test_a_nested_run_does_not_disturb_the_outer_decision(self):
        d = self.d
        d.force(FORCE_PASS)
        d.enter(4, 0x465B1F, 0, 0xA000)
        self.assertEqual(d.roll(), 1)
        d.force(FORCE_FAIL)
        d.enter(4, 0x12345678, 0, 0xB000)
        self.assertEqual(d.roll(), 0)
        d.exit()
        self.assertEqual(d.roll(), 1, "the outer decision's own roll")
        d.exit()
        # And the loop's next attempt for the outer villager continues it.
        d.enter(4, 0x465B1F, 1, 0xA000)
        self.assertEqual(d.roll(), 1)
        d.exit()
        self.assertEqual(d.draws(), 2)

    def test_the_generator_passes_about_three_times_in_four(self):
        # n fresh draws (outside any decision) from two seeds and from the
        # generator's own time-stamp seed; 75% +- 4 standard deviations, which
        # a 70% or 80% threshold falls outside.
        n = 20000
        sd = (n * 0.75 * 0.25) ** 0.5
        for seed in (0x1234567, 0xCAFEF00D, 0):
            with self.subTest(seed=seed):
                d = FixHutsDll()
                if seed:
                    d.call("VvfpFixHutsProbeSeedRoll", seed)
                passed = sum(d.roll() for _ in range(n))
                self.assertEqual(d.draws(), n)
                self.assertLess(abs(passed - 0.75 * n), 4 * sd, f"{passed}/{n}")


@unittest.skipUnless(TEST_BUILDS_PRESENT, TEST_BUILD_ABSENT)
@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
class BuilderActionFixesTests(unittest.TestCase):
    def _cave_run(self, tsc):
        return new_home(rows=("vv1_builder_action_fixes",), runtime=False, huts=(1, 1, 1), food=500, rdtsc=tsc)

    def test_alone_its_cave_rolls_and_a_failed_roll_is_stock(self):
        stock = new_home(rows=(), runtime=False, huts=(1, 1, 1), food=500)
        # 1 * 0x9E3779B9 has its top two bits set: the builder's attempt.
        m = self._cave_run(1)
        self.assertIn(BAF_CAVE, m.seen)
        self.assertIn(V1["low"], m.seen)
        self.assertEqual(v1_outcome(m), [("examine", 11)])
        # 0: the top two bits clear, a quarter of all values: the stock jump.
        m = self._cave_run(0)
        self.assertNotIn(V1["low"], m.seen)
        self.assertEqual(effects(m), effects(stock))

    def test_its_own_roll_is_three_in_four(self):
        # The cave keeps the builder's attempt unless the top two bits of
        # tsc * 0x9E3779B9 are clear; multiplying by an odd constant permutes
        # the 32-bit values, so exactly a quarter of them are clear.
        rng = random.Random(485)
        n, low = 400, 0
        for _ in range(n):
            low += V1["low"] in self._cave_run(rng.getrandbits(32)).seen
        sd = (n * 0.75 * 0.25) ** 0.5
        self.assertLess(abs(low - 0.75 * n), 4 * sd, f"{low}/{n}")

    def test_with_fix_huts_the_companion_takes_the_gate_over_and_shares_the_roll(self):
        m = new_home(rows=ROWS_BAF, force=FORCE_PASS, huts=(1, 1, 1), food=500)
        jmp = bytes(m.mu.mem_read(V1["food_site"], 5))
        target = V1["food_site"] + 5 + struct.unpack("<i", jmp[1:5])[0]
        self.assertEqual(jmp[0], 0xE9)
        self.assertTrue(BASES["fix_huts"] <= target < BASES["fix_huts"] + 0x1000000, hex(target))
        self.assertNotIn(BAF_CAVE, m.seen, "the cave's own roll is not used")
        self.assertIn(V1["low"], m.seen)
        self.assertEqual(m.draws(), 1)
        failed = new_home(rows=ROWS_BAF, force=FORCE_FAIL, huts=(1, 1, 1), food=500)
        stock = new_home(rows=(), runtime=False, huts=(1, 1, 1), food=500)
        self.assertEqual(effects(failed), effects(stock))
        self.assertEqual(failed.draws(), 1)


if __name__ == "__main__":
    unittest.main()
