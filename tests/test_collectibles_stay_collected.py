"""Picked Up Collectibles Stay Collected When Dropped (all five games): vvN_collectibles_stay_collected.

The owner (2026-11-12): a mushroom or collectible a villager has picked up is credited -- the food and Mushrooms
Found, or the collection piece (tech points / Divine Energy for a piece already found), with the tips, achievements
and completion messages -- exactly once, even when the villager is dropped elsewhere or interrupted before
delivering.  Off by default; Owner's Defaults ticks it.

Everything below RUNS the patcher's rendered bytes (and the stock bytes, to show each check can fail) in unicorn:

* The Secret City, The Tree of Life, New Believers: the item manager's release.  The game's own "put the carried
  item down" routine (VV3 0x455F30, VV4 0x45ED50, VV5 0x466420, called with -1) dispatches the old item to its
  registered listeners (VV3 0x42CE50, VV4 0x413310, VV5 0x4137C0) and empties the hands; the collectibles
  listener (VV3 0x42DEB0, VV4 0x414410, VV5 0x4146B0) awards it after testing where it was put down.  Here the
  release runs whole, twice (the second with empty hands), over each kind, at its own place and elsewhere; only
  the villager's position (VV3 0x455EF0, VV4 0x45ED00, VV5 0x466350), the map's area lookup (VV3 0x4205B0,
  VV4 0x46C3F0, VV5 0x477840) and the award's side effects (food, tech points, Divine Energy, tips, achievements:
  recorded, never run) are stand-ins.  The Tree of Life's stew pot listener (0x42EA30, registered for the
  mushrooms before the collectibles listener) runs too.
* A New Home and The Lost Children: the shipped "VVFP Collectibles Stay Collected.dll" is loaded beside the stock
  executable (or the executable as the patcher renders it with other rows) and started as VVFP Startup.dll starts
  it (tests/story_emulator.py's Process); the job builders (VV1 0x444500, VV2 0x45BCA0 / 0x45BF10) then run whole
  with the game's own queue push (VV1 0x4399F0, VV2 0x449B70) and the queue the villager keeps is played by the
  step rules of the game's villager update (VV2 0x464CD0: step 15 sets the carried item, 16 empties it, 17 runs
  the callback; VV1: step 14 runs the callback) with the real callbacks (VV2 0x461B10, VV1 0x43A230 -- the
  companion's pick detour inside it), stopping at the first walk to model a villager picked up and dropped away
  from the bin, or playing it all for a normal delivery.  The same runs without the companion started show the
  stock rule.  Every site changed by one byte: nothing installed.

What is NOT run here: the game's frame loop, the player's drag and drop itself, and the live game (not yet
verified in play).
"""
from __future__ import annotations

import functools
import hashlib
import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_fun_patcher as vfp  # noqa: E402

try:
    import pefile
    from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
    from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EIP, UC_X86_REG_ESP
    HAVE_UNICORN = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_UNICORN = False

try:
    from story_emulator import Process
    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

STOCK = ROOT / "research" / "stock-executables"
NAMES = {1: "A New Home", 2: "The Lost Children", 3: "The Secret City", 4: "The Tree of Life", 5: "New Believers"}
MODES = ("stock", "collection_progression", "immediate_fixed")
HAVE_STOCK = all((STOCK / f"Virtual Villagers - {n}.exe").is_file() for n in NAMES.values())
NEEDS = unittest.skipUnless(HAVE_UNICORN and HAVE_STOCK, "unicorn/pefile or the stock executables are missing")

ROW = "vv{}_collectibles_stay_collected"
GOLDEN = "vv{}_super_secret_golden_mushroom"
DUPLICATION = "vv{}_everyone_collects_like_vv1"
NAME = "Picked Up Collectibles Stay Collected When Dropped"

SENTINEL = 0x0BAD0000
STACK = 0x10000000
HEAP = 0x20000000


def _exe(game: int) -> Path:
    return STOCK / f"Virtual Villagers - {NAMES[game]}.exe"


@functools.lru_cache(maxsize=None)
def _image(game: int, ids: tuple[str, ...] = (), mode: str = "immediate_fixed") -> bytes:
    """The game's memory image: stock when `ids` is empty, else as the patcher renders it with those rows."""
    if ids:
        build = next(b for b in vfp.load_builds() if b.id == f"vv{game}")
        data, applied = vfp.render_patched_bytes(_exe(game), build, mode, list(ids))
        owners = {r["owner"] for r in applied}
        for rid in ids:
            # (A New Home's and The Lost Children's rows patch no executable byte: their companion does it.)
            if rid.endswith(("_super_secret_golden_mushroom", "_like_vv1")) or (
                    rid.endswith("_collectibles_stay_collected") and game not in (1, 2)):
                assert f"feature:{rid}" in owners, (rid, sorted(owners)[:5])
        data = bytes(data)
    else:
        data = _exe(game).read_bytes()
    pe = pefile.PE(data=data, fast_load=True)
    image = bytearray(pe.get_memory_mapped_image())
    size = pe.OPTIONAL_HEADER.SizeOfImage
    return bytes(image) + b"\0" * max(0, size - len(image))


def _patched(game: int, *extra: str, mode: str = "immediate_fixed") -> bytes:
    return _image(game, (ROW.format(game), *extra), mode)


class Machine:
    """A 32-bit machine over a game image: real code runs; `stub` addresses are stand-ins that record their
    arguments, pop their own and return a value."""

    def __init__(self, image: bytes):
        self.mu = Uc(UC_ARCH_X86, UC_MODE_32)
        self.mu.mem_map(0x400000, (len(image) + 0xFFF) & ~0xFFF)
        self.mu.mem_write(0x400000, image)
        self.mu.mem_map(STACK - 0x40000, 0x80000)
        self.mu.mem_map(HEAP, 0x2000000)
        self.mu.mem_map(SENTINEL, 0x1000)
        self.calls: list[tuple[int, tuple[int, ...]]] = []
        self.mu.hook_add(UC_HOOK_CODE, self._stop, begin=SENTINEL, end=SENTINEL)

    def _stop(self, uc, addr, size, data):
        uc.emu_stop()

    def stub(self, addr: int, pop: int, result=0) -> None:
        """A stand-in at `addr` that pops `pop` argument bytes; `result` is eax or fn(machine, args, ecx)."""
        def hook(uc, a, size, data):
            esp = uc.reg_read(UC_X86_REG_ESP)
            ret, *args = struct.unpack("<9I", uc.mem_read(esp, 36))
            ecx = uc.reg_read(UC_X86_REG_ECX)
            self.calls.append((addr, tuple(args[:pop // 4])))
            value = result(self, args, ecx) if callable(result) else result
            uc.reg_write(UC_X86_REG_EAX, value & 0xFFFFFFFF)
            uc.reg_write(UC_X86_REG_ESP, esp + 4 + pop)
            uc.reg_write(UC_X86_REG_EIP, ret)
        self.mu.hook_add(UC_HOOK_CODE, hook, begin=addr, end=addr)

    def call(self, entry: int, ecx: int, *args: int) -> int:
        esp = STACK - 0x100 - 4 * len(args)
        self.mu.mem_write(esp, struct.pack(f"<I{len(args)}I", SENTINEL, *[a & 0xFFFFFFFF for a in args]))
        self.mu.reg_write(UC_X86_REG_ESP, esp)
        self.mu.reg_write(UC_X86_REG_ECX, ecx)
        self.mu.emu_start(entry, 0xFFFFFFFF, count=200_000)
        assert self.mu.reg_read(UC_X86_REG_EIP) == SENTINEL, hex(self.mu.reg_read(UC_X86_REG_EIP))
        return self.mu.reg_read(UC_X86_REG_EAX)

    def rd(self, addr: int) -> int:
        return struct.unpack("<I", self.mu.mem_read(addr, 4))[0]

    def wr(self, addr: int, value: int) -> None:
        self.mu.mem_write(addr, struct.pack("<I", value & 0xFFFFFFFF))

    def count(self, addr: int) -> int:
        return sum(1 for a, _ in self.calls if a == addr)

    def args(self, addr: int) -> list[tuple[int, ...]]:
        return [args for a, args in self.calls if a == addr]


# ---------------------------------------------------------------------------------------------------------------
# The Secret City, The Tree of Life, New Believers: the release.
# ---------------------------------------------------------------------------------------------------------------
# game: the release routine, the carried field, the item manager, the collectibles listener object and vtable,
# the listener's per-kind count array (object + 4 x kind + this), the position and area stand-ins (and the area
# manager), the food writer and the Mushrooms Found counter, the tech points and tip stand-ins.
RELEASE = {
    3: dict(release=0x455F30, carried=0xF20, manager=0x58EDB8, listener=0x58F428, vtable=0x482938, counts=0x10,
            position=(0x455EF0, 4), area=(0x4205B0, 8),
            stubs={0x427130: 4, 0x436E60: 0xC, 0x412CD0: 4},
            food=(0x4263F0, 4), found=0x5824B4,
            kinds={"collectible": (0x34, 0x19), "uncommon": (0x38, 0x19), "rare": (0x3C, 0x19),
                   "tablet": (0x58, 0x19), "brown": (0x64, 0x0E), "red": (0x65, 0x0E)}),
    4: dict(release=0x45ED50, carried=0x1CDC, manager=0x4CC0A0, listener=0x4CC838, vtable=0x48C4D8, counts=-0x38,
            position=(0x45ED00, 4), area=(0x46C3F0, 8),
            stubs={0x41E300: 4, 0x412F90: 8, 0x44B890: 0xC, 0x46D880: 4, 0x468C60: 0, 0x45DEC0: 8, 0x438A30: 4,
                   0x42DC80: 0},
            food=(0x41D920, 4), found=0x4D6DF4,
            # every area: collectibles already count anywhere in the stock game
            kinds={"fish scale": (0x46, None), "lab equipment": (0x52, None), "mural": (0x5E, None),
                   "flute": (0x6A, None), "brown": (0x76, 8), "red": (0x77, 8)}),
    5: dict(release=0x466420, carried=0x1D0C, manager=0x4DB790, listener=0x4DBFC8, vtable=0x4974F8, counts=0x630,
            position=(0x466350, 4), area=(0x477840, 8),
            stubs={0x425950: 0, 0x424F80: 4, 0x4237B0: 4, 0x413450: 8, 0x44E840: 4, 0x44E730: 0xC},
            food=(0x41EB40, 4), found=0x51D36C,
            kinds={"lab gear": (0x50, 0x0D), "lab gear rare": (0x67, 0x0D), "relic": (0x68, 0x36),
                   "relic rare": (0x7F, 0x36), "brown": (0x80, 5), "red": (0x81, 5)}),
}
POT = {"listener": 0x4D76DC, "vtable": 0x48E258}     # The Tree of Life's stew pot, registered first (0x41345D)
ELSEWHERE = 0x2B                                     # an area no listener asks for
VILLAGER = HEAP + 0x100000


def _release_machine(game: int, image: bytes, kind: int, area: int, *, pot_takes: bool = False) -> Machine:
    r = RELEASE[game]
    m = Machine(image)
    m.wr(r["listener"], r["vtable"])
    slot = r["manager"] + kind * 16
    listeners = [r["listener"]]
    if game == 4 and kind in (0x76, 0x77, 0x78):
        m.wr(POT["listener"], POT["vtable"])
        listeners = [POT["listener"], r["listener"]]
        m.wr(VILLAGER + 0x1CE0, 0x3E if pot_takes else 0)    # a villager bringing the stew an ingredient
    for i, obj in enumerate(listeners):
        m.wr(slot + 4 * i, obj)
    m.wr(slot + 0xC, len(listeners))
    m.wr(VILLAGER + r["carried"], kind)

    def position(machine, args, ecx):
        machine.wr(args[0], 700)
        machine.wr(args[0] + 4, 500)
        return args[0]
    m.stub(r["position"][0], r["position"][1], position)
    m.stub(r["area"][0], r["area"][1], area)
    for addr, pop in r["stubs"].items():
        m.stub(addr, pop, 1 if addr == 0x46D880 else 0)   # VV4 0x46D880: the stew pot's technology is there
    m.stub(r["food"][0], r["food"][1])
    return m


def _credits(game: int, image: bytes, kind: int, area: int, **kw) -> dict:
    """Release the carried `kind` at `area`, then release again with empty hands; what was credited."""
    r = RELEASE[game]
    m = _release_machine(game, image, kind, area, **kw)
    count_at = r["listener"] + kind * 4 + r["counts"]
    for _ in range(2):
        m.call(r["release"], VILLAGER, 0xFFFFFFFF)
    return {"piece": m.rd(count_at), "food": [a[0] for a in m.args(r["food"][0])], "found": m.rd(r["found"]),
            "hands": m.rd(VILLAGER + r["carried"]), "pot": m.rd(POT["listener"] + 0x14) if game == 4 else 0,
            "machine": m}


@NEEDS
class LaterGamesReleaseTests(unittest.TestCase):
    def _check(self, game: int, image: bytes, patched: bool) -> None:
        for name, (kind, home) in RELEASE[game]["kinds"].items():
            mushroom = name in ("brown", "red")
            for where, area in (("home", home if home is not None else ELSEWHERE), ("elsewhere", ELSEWHERE)):
                with self.subTest(game=game, kind=name, where=where, patched=patched):
                    got = _credits(game, image, kind, area)
                    expected = 1 if (where == "home" or patched or home is None) else 0
                    self.assertEqual(got["hands"], 0xFFFFFFFF, "the hands are empty after the release")
                    if mushroom:
                        self.assertEqual(len(got["food"]), expected, got["food"])
                        self.assertEqual(got["found"], expected, "Mushrooms Found")
                        self.assertEqual(got["piece"], 0)
                    else:
                        self.assertEqual(got["piece"], expected, "the piece is counted once")
                        self.assertEqual(got["food"], [])

    def test_stock_counts_only_at_home(self):
        for game in RELEASE:
            self._check(game, _image(game), patched=False)

    def test_patched_counts_once_anywhere_in_every_mode(self):
        for game in RELEASE:
            for mode in MODES:
                self._check(game, _patched(game, mode=mode), patched=True)

    def test_with_golden_mushroom_and_the_duplication_cheat(self):
        """The golden kind pays 100 food anywhere, once; with the Duplication Cheat each child's release counts
        once (two children, two releases, two credits)."""
        golden = {3: 0x66, 4: 0x78, 5: 0x82}
        for game in RELEASE:
            image = _patched(game, GOLDEN.format(game), DUPLICATION.format(game))
            with self.subTest(game=game):
                got = _credits(game, image, golden[game], ELSEWHERE)
                self.assertEqual(got["food"], [100])
                self.assertEqual(got["found"], 1)
                # two children who both picked the same item: each release counts once
                r = RELEASE[game]
                kind = RELEASE[game]["kinds"]["brown"][0]
                m = _release_machine(game, image, kind, ELSEWHERE)
                other = VILLAGER + 0x40000
                m.wr(other + r["carried"], kind)
                for villager in (VILLAGER, other, VILLAGER, other):
                    m.call(r["release"], villager, 0xFFFFFFFF)
                self.assertEqual(len(m.args(r["food"][0])), 2)
                self.assertEqual(m.rd(r["found"]), 2)

    def test_with_every_other_patch(self):
        for game in RELEASE:
            others = _others(game)
            image = _image(game, tuple(others + [ROW.format(game)]))
            for name in ("brown", "red"):
                kind, home = RELEASE[game]["kinds"][name]
                with self.subTest(game=game, kind=name):
                    got = _credits(game, image, kind, ELSEWHERE)
                    self.assertEqual(len(got["food"]), 1)
                    self.assertEqual(got["found"], 1)

    def test_tree_of_life_stew_pot(self):
        """At the stew pot (area 5) the pot's own listener runs first, as in the stock game: an ingredient it takes
        goes in the pot; either way the mushroom never also pays food there."""
        for image, label in ((_image(4), "stock"), (_patched(4), "patched")):
            for takes in (False, True):
                with self.subTest(build=label, pot_takes=takes):
                    got = _credits(4, image, 0x76, 5, pot_takes=takes)
                    self.assertEqual(got["food"], [])
                    self.assertEqual(got["found"], 0)
                    self.assertEqual(got["pot"], 1 if takes else 0)


# ---------------------------------------------------------------------------------------------------------------
# A New Home and The Lost Children: "VVFP Collectibles Stay Collected.dll" on the executable, started as VVFP
# Startup.dll starts it.
# ---------------------------------------------------------------------------------------------------------------
DLL = ROOT / "assets" / "collectibles_stay_collected" / "VVFP Collectibles Stay Collected.dll"
DLL_NAME = "VVFP Collectibles Stay Collected.dll"
NEEDS_DLL = unittest.skipUnless(HAVE_UNICORN and HAVE_EMULATOR and HAVE_STOCK and DLL.is_file(),
                                "unicorn/pefile, the stock executables or the companion are missing")
# The detours: (VA, stock bytes, the stock code the companion checks first (VA, bytes) or None).
DETOURS = {
    1: [(0x43A266, "5F5D5B5EC20800", (0x43A24B, "8B8610E00300C780ACAC0000010000008B8E24E00300E81AC1FDFF")),
        (0x444670, "E87B53FFFF", None)],
    2: [(0x45BE4D, "E81EDDFEFF", (0x45BE4A, "6A1157")),
        (0x45C09A, "E8D1DAFEFF", (0x45C095, "6A11578BCE"))],
}


def _exe_bytes(game: int, ids: tuple[str, ...] = (), mode: str = "immediate_fixed") -> bytes:
    """The executable as the patcher renders it with `ids` (stock when empty)."""
    if not ids:
        return _exe(game).read_bytes()
    return _rendered(game, tuple(ids), mode)


@functools.lru_cache(maxsize=None)
def _rendered(game: int, ids: tuple[str, ...], mode: str) -> bytes:
    build = next(b for b in vfp.load_builds() if b.id == f"vv{game}")
    data, _ = vfp.render_patched_bytes(_exe(game), build, mode, list(ids))
    return bytes(data)


class Game:
    """The executable in memory with the companion loaded; `with_dll` False leaves the game stock (the companion is
    not started).  Stand-ins (`stub`) record their arguments, pop their own and return a value."""

    def __init__(self, game: int, exe: bytes | None = None, *, with_dll: bool = True):
        self.game = game
        self.p = Process(exe if exe is not None else _exe(game).read_bytes(), DLL)
        self.calls: list[tuple[int, tuple[int, ...]]] = []
        self.installed = 0
        if with_dll:
            self.p.export("VvfpStartup", game, 0)
            self.installed = self.p.export("VvfpCollectiblesStayCollectedInstalled")

    def stub(self, va: int, pop: int, result=0) -> None:
        def fn(p):
            args = tuple(p.arg(i) for i in range(8))
            self.calls.append((va, args[:pop // 4]))
            value = result(self, args, p.reg("ecx")) if callable(result) else result
            return value & 0xFFFFFFFF, pop
        self.p.stub(va, fn)

    def call(self, va: int, ecx: int, *args: int) -> int:
        return self.p.call(va, [a & 0xFFFFFFFF for a in args], ecx=ecx, limit=500_000)

    def rd(self, va: int) -> int:
        return self.p.u32(va)

    def wr(self, va: int, value: int) -> None:
        self.p.put32(va, value)

    def args(self, va: int) -> list[tuple[int, ...]]:
        return [a for v, a in self.calls if v == va]

    def queue(self, record: int, length: int) -> list[tuple[int, int]]:
        """The villager's step queue as the game keeps it: (step, param) of each entry, to the first empty one."""
        out = []
        for i in range(length):
            step, *_rest, param = struct.unpack("<6I", self.p.read(record + i * 24, 24))
            if step == 0:
                break
            out.append((step, param))
        return out


def _others(game: int) -> list[str]:
    alts = set(vfp.ALTERNATIVE_FUN_PATCH_IDS)
    return [p.id for p in vfp.load_public_fun_patches()
            if p.game_id == f"vv{game}" and p.id not in alts and p.id != ROW.format(game)]


# ---------------------------------------------------------------------------------------------------------------
# The Lost Children: the job builders run whole with the game's own queue push; the queue the child keeps is then
# played by the step rules of the game's villager update (0x464CD0: step 15 sets the carried item, 16 empties it,
# 17 runs the callback) with the real callbacks (0x461B10), stopping at the first walk (3) to model a child picked
# up and dropped elsewhere, or playing it all for a normal delivery.
# ---------------------------------------------------------------------------------------------------------------
VV2 = dict(mushroom=0x45BCA0, collectible=0x45BF10, callback=0x461B10, record=0xE48C, queue=0x4C, length=0x31,
           food=0x4262B0, tech=0x426290,
           stubs={0x441680: 4, 0x4682BD: 0, 0x4454E0: 8, 0x44FBB0: 4, 0x415350: 0, 0x4257A0: 8, 0x426120: 4})
SLOT = 3


class LostChildren:
    def __init__(self, exe: bytes | None = None, *, with_dll: bool = True):
        self.g = g = Game(2, exe, with_dll=with_dll)
        self.mgr = g.p.alloc(0xE58000)
        self.state = g.p.alloc(0x40000)
        self.ctx = g.p.alloc(0x1000)
        g.wr(self.mgr + 0xE574F4, self.ctx)
        g.wr(self.mgr + 0xE574D4, self.state)
        g.wr(self.mgr + 0xE574F0, self.ctx + 0x100)
        for slot in range(8):
            g.wr(self.mgr + slot * VV2["record"] + 4, 500)
            g.wr(self.mgr + slot * VV2["record"] + 8, 600)
        g.stub(0x4031A0, 0, 60)                            # rand: never the optional steps' branch
        for addr, pop in VV2["stubs"].items():
            g.stub(addr, pop)
        g.stub(VV2["food"], 4)
        g.stub(VV2["tech"], 4)

    def steps(self, slot: int = SLOT) -> list[tuple[int, int]]:
        return self.g.queue(self.mgr + slot * VV2["record"] + VV2["queue"], VV2["length"])

    def build(self, job: str, item: int, slot: int = SLOT) -> list[tuple[int, int]]:
        self.g.wr(self.ctx + 0x28, item)
        self.g.call(VV2[job], self.mgr, slot)
        return self.steps(slot)

    def play(self, interrupted: bool, slot: int = SLOT) -> None:
        record = self.mgr + slot * VV2["record"]
        for step, param in self.steps(slot):
            if step == 3 and interrupted:
                return
            if step == 0xF:
                self.g.wr(record + 0x44, param)
            elif step == 0x10:
                self.g.wr(record + 0x44, 0x1A)
            elif step == 0x11 and param in (0x27, 0x28, 0x29):
                self.g.call(VV2["callback"], self.mgr, slot, param)

    def food(self) -> list[int]:
        return [a[0] for a in self.g.args(VV2["food"])]

    def found(self) -> int:
        return self.g.rd(self.state + 0x2E50C)


@NEEDS_DLL
class LostChildrenTests(unittest.TestCase):
    def mushroom(self, exe, item: int, interrupted: bool, *, with_dll: bool = True):
        v = LostChildren(exe, with_dll=with_dll)
        steps = v.build("mushroom", item)
        v.play(interrupted)
        return v.food(), v.found(), steps

    def test_the_companion_installs_on_the_stock_game(self):
        v = LostChildren()
        self.assertEqual(v.g.installed, 1)
        for va, stock, _check in DETOURS[2]:
            self.assertEqual(v.g.p.read(va, 1), b"\xE8")
            self.assertNotEqual(v.g.p.read(va, 5).hex().upper(), stock)

    def test_the_queue_puts_the_award_right_after_the_carry_step(self):
        for item, award in ((0x30, 0x27), (0x31, 0x28)):
            stock = self.mushroom(None, item, False, with_dll=False)[2]
            for with_dll in (False, True):
                with self.subTest(item=hex(item), with_dll=with_dll):
                    steps = self.mushroom(None, item, False, with_dll=with_dll)[2]
                    carry = steps.index((0xF, item + 0x1E))
                    self.assertEqual(steps.count((0x11, award)), 1, "one award step")
                    self.assertEqual(steps.index((0x11, award)) == carry + 1, with_dll)
                    # the same steps, only the award moved; the rest keep their order
                    self.assertEqual(sorted(steps), sorted(stock))
                    self.assertEqual([s for s in steps if s != (0x11, award)],
                                     [s for s in stock if s != (0x11, award)])

    def test_mushroom_counts_once_dropped_away_or_delivered(self):
        for item, food in ((0x30, 6), (0x31, 35)):
            for interrupted in (True, False):
                with self.subTest(item=hex(item), interrupted=interrupted):
                    self.assertEqual(self.mushroom(None, item, interrupted)[:2], ([food], 1))
                    stock = self.mushroom(None, item, interrupted, with_dll=False)[:2]
                    self.assertEqual(stock, ([], 0) if interrupted else ([food], 1))

    def test_golden_mushroom_pays_100_once(self):
        exe = _exe_bytes(2, (GOLDEN.format(2), DUPLICATION.format(2), ROW.format(2)))
        for interrupted in (True, False):
            with self.subTest(interrupted=interrupted):
                self.assertEqual(self.mushroom(exe, 0x32, interrupted)[:2], ([100], 1))

    def test_the_duplication_cheat_credits_each_child_once(self):
        """Two children dropped on the same mushroom (the cheat lets both take it): each builds its own job, each
        is dropped away from the bin, each credits once -- two credits in all."""
        exe = _exe_bytes(2, (GOLDEN.format(2), DUPLICATION.format(2), ROW.format(2)))
        v = LostChildren(exe)
        self.assertEqual(v.g.installed, 1)
        for slot in (3, 5):
            v.build("mushroom", 0x31, slot)
        for slot in (3, 5):
            v.play(True, slot)
        self.assertEqual((v.food(), v.found()), ([35, 35], 2))

    def test_collectible_counts_once_dropped_away_or_delivered(self):
        piece = 0x1E + 5                                   # carried value of piece 5 (a butterfly)
        for with_dll in (False, True):
            for interrupted in (True, False):
                for owned in (False, True):
                    with self.subTest(with_dll=with_dll, interrupted=interrupted, owned=owned):
                        v = LostChildren(with_dll=with_dll)
                        v.g.p.write(v.state + piece + 0x2E702, bytes([1 if owned else 0]))
                        steps = v.build("collectible", 5)
                        carry = steps.index((0xF, piece))
                        self.assertEqual(steps.count((0x11, 0x29)), 1, "one award step")
                        self.assertEqual(steps.index((0x11, 0x29)) == carry + 1, with_dll)
                        v.play(interrupted)
                        credited = not (interrupted and not with_dll)
                        found = v.g.p.read(v.state + piece + 0x2E702, 1)[0]
                        self.assertEqual(found, 1 if (credited or owned) else 0)
                        self.assertEqual(len(v.g.args(VV2["tech"])), 1 if (credited and owned) else 0)

    def test_a_full_queue_is_left_as_the_game_left_it(self):
        """The companion's stub, as the job's award call reaches it: on a full queue the game's push adds nothing and
        nothing is moved; with room, the new award goes right after the carry step, the rest in order."""
        v = LostChildren()
        record = v.mgr + SLOT * VV2["record"] + VV2["queue"]
        entries = [(0xF, 0x4E)] + [(0x16, 7)] * (VV2["length"] - 1)
        for i, (step, param) in enumerate(entries):
            v.g.p.write(record + i * 24, struct.pack("<6I", step, 0, 0, 0, 0, param))
        stub = 0x45BE4D + 5 + struct.unpack("<i", v.g.p.read(0x45BE4E, 4))[0]
        v.g.p.call(stub, [SLOT, 0x11, 0, 0, 0, 0, 0x27], ecx=v.mgr)
        self.assertEqual(v.steps(), entries)
        v.g.p.write(record + (VV2["length"] - 1) * 24, bytes(24))
        v.g.p.call(stub, [SLOT, 0x11, 0, 0, 0, 0, 0x27], ecx=v.mgr)
        self.assertEqual(v.steps(), [(0xF, 0x4E), (0x11, 0x27)] + [(0x16, 7)] * (VV2["length"] - 2))

    def test_with_every_other_patch_in_every_mode(self):
        others = _others(2)
        self.assertGreater(len(others), 10)
        for mode in MODES:
            exe = _exe_bytes(2, tuple(others + [ROW.format(2)]), mode)
            with self.subTest(mode=mode):
                for va, stock, check in DETOURS[2]:
                    self.assertEqual(_va_bytes(exe, va, len(stock) // 2), stock, hex(va))
                v = LostChildren(exe)
                self.assertEqual(v.g.installed, 1)
                v.build("mushroom", 0x31)
                v.play(True)
                self.assertEqual((v.food(), v.found()), ([35], 1))


# ---------------------------------------------------------------------------------------------------------------
# A New Home: the mushroom job runs whole with the game's own queue push; the queue is then played with the real
# callback dispatcher (step 14 runs callback [entry + 0x14]), stopping at the first walk for a villager dropped
# away from the food store.
# ---------------------------------------------------------------------------------------------------------------
VV1 = dict(job=0x444500, dispatch=0x43A230, food=0x41D140, found=0x9E30, kind=0xACB0, picked=0xACAC,
           record=0x3D8, queue=0x44, length=0x1D,
           stubs={0x433970: 4, 0x44B23D: 0, 0x43DEF0: 4, 0x416380: 0, 0x41C960: 8})


class NewHome:
    def __init__(self, exe: bytes | None = None, *, with_dll: bool = True):
        self.g = g = Game(1, exe, with_dll=with_dll)
        self.array = g.p.alloc(0x40000)
        self.mgr = g.p.alloc(0x10000)
        g.wr(self.array + 0x3E010, self.mgr)
        g.wr(self.array + 0x3E02C, self.array + 0x3F000)
        g.wr(self.array + 0x3E024, self.array + 0x3F100)
        g.stub(0x402F10, 0, 1)
        for addr, pop in VV1["stubs"].items():
            g.stub(addr, pop)
        g.stub(VV1["food"], 4)

    def steps(self, slot: int = SLOT) -> list[tuple[int, int]]:
        return self.g.queue(self.array + slot * VV1["record"] + VV1["queue"], VV1["length"])

    def run(self, kind: int, interrupted: bool, slot: int = SLOT) -> list[tuple[int, int]]:
        self.g.wr(self.mgr + VV1["kind"], kind)
        self.g.call(VV1["job"], self.array, slot)
        steps = self.steps(slot)
        for step, param in steps:
            if step == 3 and interrupted:
                break
            if step == 0xE:
                self.g.call(VV1["dispatch"], self.array, slot, param)
        return steps

    def food(self) -> list[int]:
        return [a[0] for a in self.g.args(VV1["food"])]

    def found(self) -> int:
        return self.g.rd(self.mgr + VV1["found"])


def _va_bytes(exe: bytes, va: int, n: int) -> str:
    pe = pefile.PE(data=exe, fast_load=True)
    off = pe.get_offset_from_rva(va - 0x400000)
    return exe[off:off + n].hex().upper()


@NEEDS_DLL
class NewHomeTests(unittest.TestCase):
    def test_the_companion_installs_on_the_stock_game(self):
        v = NewHome()
        self.assertEqual(v.g.installed, 1)
        self.assertEqual(v.g.p.read(0x43A266, 1), b"\xE9")
        self.assertEqual(v.g.p.read(0x43A26B, 2), b"\x90\x90")
        self.assertEqual(v.g.p.read(0x444670, 1), b"\xE8")
        self.assertNotEqual(v.g.p.read(0x444670, 5).hex().upper(), "E87B53FFFF")

    def test_the_job_queues_the_pick_and_no_end_of_trip_award(self):
        for kind, award in ((0, 0x20), (1, 0x21)):
            with self.subTest(kind=kind):
                stock = NewHome(with_dll=False).run(kind, False)
                patched = NewHome().run(kind, False)
                self.assertIn((0xE, 0x2A), stock)
                self.assertIn((0xE, award), stock)
                self.assertEqual([s for s in stock if s != (0xE, award)], patched, "only the award step is gone")

    def test_mushroom_counts_once_at_the_pick(self):
        for kind, food in ((0, 8), (1, 45)):
            for interrupted in (True, False):
                with self.subTest(kind=kind, interrupted=interrupted):
                    v = NewHome()
                    v.run(kind, interrupted)
                    self.assertEqual((v.food(), v.found(), v.g.rd(v.mgr + VV1["picked"])), ([food], 1, 1))
                    s = NewHome(with_dll=False)
                    s.run(kind, interrupted)
                    self.assertEqual((s.food(), s.found()), ([], 0) if interrupted else ([food], 1))

    def test_golden_mushroom_pays_100_once(self):
        exe = _exe_bytes(1, (GOLDEN.format(1), ROW.format(1)))
        for kind, food in ((2, 100), (0, 8), (1, 45)):
            for interrupted in (True, False):
                with self.subTest(kind=kind, interrupted=interrupted):
                    v = NewHome(exe)
                    self.assertEqual(v.g.installed, 1)
                    v.run(kind, interrupted)
                    self.assertEqual((v.food(), v.found()), ([food], 1))

    def test_several_villagers_on_one_mushroom_each_count_once(self):
        """A New Home's own rule (the one the Duplication Cheat brings to the later games): each villager dropped
        on the mushroom picks it, and each pick counts once."""
        v = NewHome()
        for slot in (3, 5):
            v.run(1, True, slot)
        self.assertEqual((v.food(), v.found()), ([45, 45], 2))

    def test_with_every_other_patch_in_every_mode(self):
        others = _others(1)
        self.assertGreater(len(others), 10)
        for mode in MODES:
            exe = _exe_bytes(1, tuple(others + [ROW.format(1)]), mode)
            with self.subTest(mode=mode):
                for va, stock, check in DETOURS[1]:
                    self.assertEqual(_va_bytes(exe, va, len(stock) // 2), stock, hex(va))
                v = NewHome(exe)
                self.assertEqual(v.g.installed, 1)
                for kind, food in ((0, 8), (1, 45), (2, 100)):
                    v.g.calls.clear()
                    v.g.wr(v.mgr + VV1["found"], 0)
                    v.run(kind, True)
                    self.assertEqual((v.food(), v.found()), ([food], 1), (mode, kind))


@NEEDS_DLL
class AllOrNoneTests(unittest.TestCase):
    def test_a_site_that_is_not_stock_installs_nothing(self):
        for game in (1, 2):
            sites = DETOURS[game]
            spots = [(va, stock) for va, stock, _c in sites] + [c for _va, _s, c in sites if c is not None]
            for va, stock in spots:
                with self.subTest(game=game, changed=hex(va)):
                    data = bytearray(_exe(game).read_bytes())
                    pe = pefile.PE(data=bytes(data), fast_load=True)
                    off = pe.get_offset_from_rva(va - 0x400000)
                    data[off] ^= 0xFF
                    g = Game(game, bytes(data))
                    self.assertEqual(g.installed, 0)
                    for other_va, other_stock, _c in sites:
                        if other_va != va:
                            self.assertEqual(g.p.read(other_va, len(other_stock) // 2).hex().upper(), other_stock)

    def test_another_game_installs_nothing(self):
        for game, exe_game in ((3, 1), (4, 2), (5, 2)):
            g = Game(exe_game, with_dll=False)
            g.p.export("VvfpStartup", game, 0)
            self.assertEqual(g.p.export("VvfpCollectiblesStayCollectedInstalled"), 0)
            for va, stock, _c in DETOURS[exe_game]:
                self.assertEqual(g.p.read(va, len(stock) // 2).hex().upper(), stock)


# ---------------------------------------------------------------------------------------------------------------
# The rows, the defaults and the documents.
# ---------------------------------------------------------------------------------------------------------------
class RowTests(unittest.TestCase):
    def test_rows_and_defaults(self):
        from vv_fun_patcher_gui import (
            DEFAULT_OFF_FUN_PATCH_IDS, OWNERS_DEFAULT_OFF_FUN_PATCH_IDS, default_fun_patch_selection,
            owners_default_fun_patch_selection)
        rows = {p.id: p.raw for p in vfp.load_fun_patches()}
        public = {p.id for p in vfp.load_public_fun_patches()}
        for game in NAMES:
            rid = ROW.format(game)
            with self.subTest(game=game):
                self.assertIn(rid, public)
                self.assertEqual(rows[rid]["name"], NAME)
                self.assertEqual(rows[rid]["game_id"], f"vv{game}")
                self.assertIn("**Needs no other patch.**", rows[rid]["description"])
                self.assertIn(rid, DEFAULT_OFF_FUN_PATCH_IDS)
                self.assertNotIn(rid, OWNERS_DEFAULT_OFF_FUN_PATCH_IDS)
                self.assertFalse(default_fun_patch_selection(rid))
                self.assertTrue(owners_default_fun_patch_selection(rid))
                # The golden mushroom stays a secret: no word of it in this row.
                self.assertNotIn("golden", json.dumps(rows[rid]).lower())
        self.assertIn("mushroom", rows[ROW.format(1)]["description"].lower())
        self.assertNotIn("collectible piece", rows[ROW.format(1)]["description"].lower())

    def test_vv1_and_vv2_ship_the_companion_and_no_executable_byte(self):
        rows = {p.id: p.raw for p in vfp.load_fun_patches()}
        digest = hashlib.sha256(DLL.read_bytes()).hexdigest().upper() if DLL.is_file() else None
        for game in (1, 2):
            row = rows[ROW.format(game)]
            with self.subTest(game=game):
                self.assertEqual(row["patches"], [])
                self.assertEqual([(c["source"], c["destination"]) for c in row["companion_files"]],
                                 [("assets/collectibles_stay_collected/" + DLL_NAME, DLL_NAME)])
                if digest is not None:
                    self.assertEqual(row["companion_files"][0]["sha256"], digest)
                self.assertIn(DLL_NAME, row["description"])
                self.assertEqual([(int(d["va"], 16), d["stock_bytes"]) for d in row["runtime_detours"]],
                                 [(va, stock) for va, stock, _c in DETOURS[game]])
                for d in row["runtime_detours"]:
                    self.assertEqual(len(d["written_bytes"]), len(d["stock_bytes"]))
        self.assertIn(DLL_NAME, vfp.STARTUP_LOADER_COMPANIONS_2)
        for game in (3, 4, 5):
            self.assertNotIn("companion_files", rows[ROW.format(game)])
            self.assertTrue(rows[ROW.format(game)]["patches"])

    def test_the_detours_are_the_ones_the_companion_holds(self):
        source = (ROOT / "native" / "vvfp_collectibles_stay_collected" /
                  "vvfp_collectibles_stay_collected.c").read_text(encoding="utf-8")
        for game in (1, 2):
            for va, stock, check in DETOURS[game]:
                self.assertIn(f"0x{va:X}u", source)
                written = ", ".join(f"0x{b:02X}" for b in bytes.fromhex(stock))
                self.assertIn(written, source, (game, hex(va)))
                if check is not None:
                    self.assertIn(f"0x{check[0]:X}" if game == 1 else "_PUSHES", source)

    @NEEDS
    def test_no_other_row_claims_a_site(self):
        for game in (1, 2):
            pe = pefile.PE(str(_exe(game)), fast_load=True)
            ranges = []
            for va, stock, check in DETOURS[game]:
                ranges.append((va, va + len(stock) // 2))
                if check is not None:
                    ranges.append((check[0], check[0] + len(check[1]) // 2))
            for p in vfp._load_fun_patch_records():
                if p.raw.get("game_id") != f"vv{game}" or p.id == ROW.format(game):
                    continue
                claims = []
                for patch in p.raw.get("patches", []) or []:
                    rva = pe.get_rva_from_offset(int(patch["offset"], 16))
                    if rva is not None:                        # (bytes past the stock file: a new section)
                        claims.append((0x400000 + rva, len(patch.get("before", "")) // 2 or 1))
                for d in p.raw.get("runtime_detours", []) or []:
                    claims.append((int(str(d["va"]), 0), len(bytes.fromhex(d["stock_bytes"]))))
                for va, n in claims:
                    for start, end in ranges:
                        self.assertFalse(va < end and start < va + n, (p.id, hex(va), hex(start)))

    @NEEDS
    def test_stock_bytes(self):
        rows = {p.id: p.raw for p in vfp.load_fun_patches()}
        for game in NAMES:
            data = _exe(game).read_bytes()
            for p in rows[ROW.format(game)]["patches"]:
                off = int(p["offset"], 16)
                with self.subTest(game=game, offset=p["offset"]):
                    self.assertEqual(data[off:off + len(p["before"]) // 2].hex().upper(), p["before"])
            for d in rows[ROW.format(game)].get("runtime_detours", []):
                with self.subTest(game=game, va=d["va"]):
                    self.assertEqual(_va_bytes(data, int(d["va"], 16), len(d["stock_bytes"]) // 2),
                                     d["stock_bytes"])

    def test_readme_and_guide(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        guides = json.loads((ROOT / "data" / "how_to_use.json").read_text(encoding="utf-8"))
        ids = {i for e in guides["patches"] for i in e["ids"]}
        for game in NAMES:
            self.assertIn(f"`{ROW.format(game)}`", readme)
            self.assertIn(ROW.format(game), ids)


if __name__ == "__main__":
    unittest.main()
