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
* The Lost Children and A New Home: the job builders (VV2 0x45BCA0 / 0x45BF10, VV1 0x444500) run whole and their
  queued steps are recorded (VV2 0x449B70, VV1 0x4399F0 stand-ins); the queue is then played by the step rules
  of the game's villager update (VV2 0x464CD0: step 15 sets the carried item, 16 empties it, 17 runs the
  callback; VV1: step 14 runs the callback) with the real callbacks (VV2 0x461B10, VV1 0x43A230), stopping at
  the first walk to model a child picked up and dropped elsewhere, or playing it all for a normal delivery.

What is NOT run here: the game's frame loop, the player's drag and drop itself, and the live game (not yet
verified in play).
"""
from __future__ import annotations

import functools
import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as vfp  # noqa: E402

try:
    import pefile
    from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
    from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EIP, UC_X86_REG_ESP
    HAVE_UNICORN = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_UNICORN = False

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
            if rid.endswith(("_collectibles_stay_collected", "_super_secret_golden_mushroom", "_like_vv1")):
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


def _others(game: int) -> list[str]:
    alts = set(vfp.ALTERNATIVE_FUN_PATCH_IDS)
    return [p.id for p in vfp.load_public_fun_patches()
            if p.game_id == f"vv{game}" and p.id not in alts and p.id != ROW.format(game)]


# ---------------------------------------------------------------------------------------------------------------
# The Lost Children: the job builders' queues, played with the real callbacks.
# ---------------------------------------------------------------------------------------------------------------
VV2 = dict(mushroom=0x45BCA0, collectible=0x45BF10, queue=0x449B70, callback=0x461B10, record=0xE48C,
           food=0x4262B0, tech=0x426290,
           stubs={0x4492A0: 4, 0x441680: 4, 0x4682BD: 0, 0x4454E0: 8, 0x44FBB0: 4, 0x415350: 0, 0x4257A0: 8,
                  0x426120: 4})
MGR = HEAP
STATE = HEAP + 0x1000000
CTX = HEAP + 0x1800000
SLOT = 3


def _vv2(image: bytes, item: int) -> Machine:
    m = Machine(image)
    m.wr(MGR + 0xE574F4, CTX)
    m.wr(CTX + 0x28, item)
    m.wr(MGR + 0xE574D4, STATE)
    m.wr(MGR + 0xE574F0, CTX + 0x100)
    m.wr(MGR + SLOT * VV2["record"] + 4, 500)
    m.wr(MGR + SLOT * VV2["record"] + 8, 600)
    m.stub(VV2["queue"], 0x1C)
    m.stub(0x4031A0, 0, 60)                            # rand: never the optional steps' branch
    for addr, pop in VV2["stubs"].items():
        m.stub(addr, pop)
    m.stub(VV2["food"], 4)
    m.stub(VV2["tech"], 4)
    return m


def _vv2_play(m: Machine, interrupted: bool) -> None:
    """Play the recorded queue by the villager update's rules: 15 carry, 16 empty hands, 17 callback (the award
    callbacks 39..41 run for real; the pickups 62/63 take the item off the map and are not needed here); a walk
    (3) is where a child picked up by the player stops."""
    record = MGR + SLOT * VV2["record"]
    for args in m.args(VV2["queue"]):
        slot, step, *_rest, arg = args
        if step == 3 and interrupted:
            return
        if step == 0xF:
            m.wr(record + 0x44, arg)
        elif step == 0x10:
            m.wr(record + 0x44, 0x1A)
        elif step == 0x11 and arg in (0x27, 0x28, 0x29):
            m.call(VV2["callback"], MGR, SLOT, arg)


@NEEDS
class LostChildrenTests(unittest.TestCase):
    def _mushroom(self, image: bytes, item: int, interrupted: bool) -> tuple[list, int, list]:
        m = _vv2(image, item)
        m.call(VV2["mushroom"], MGR, SLOT)
        steps = [(a[1], a[-1]) for a in m.args(VV2["queue"])]
        _vv2_play(m, interrupted)
        return [a[0] for a in m.args(VV2["food"])], m.rd(STATE + 0x2E50C), steps

    def test_the_queue_puts_the_award_right_after_the_carry_step(self):
        for item, award in ((0x30, 0x27), (0x31, 0x28)):
            for image, patched in ((_image(2), False), (_patched(2), True)):
                with self.subTest(item=hex(item), patched=patched):
                    steps = self._mushroom(image, item, False)[2]
                    carry = steps.index((0xF, item + 0x1E))
                    self.assertEqual(steps.count((0x11, award)), 1, "one award step")
                    at = steps.index((0x11, award))
                    self.assertEqual(at == carry + 1, patched)
                    # the same steps, only the award moved
                    stock_steps = self._mushroom(_image(2), item, False)[2]
                    self.assertEqual(sorted(steps), sorted(stock_steps))

    def test_mushroom_counts_once_dropped_or_delivered(self):
        for mode in MODES:
            for item, food in ((0x30, 6), (0x31, 35)):
                for interrupted in (True, False):
                    with self.subTest(mode=mode, item=hex(item), interrupted=interrupted):
                        got, found, _ = self._mushroom(_patched(2, mode=mode), item, interrupted)
                        self.assertEqual((got, found), ([food], 1))
                        stock, stock_found, _ = self._mushroom(_image(2), item, interrupted)
                        self.assertEqual((stock, stock_found), ([] if interrupted else [food], 0 if interrupted else 1))

    def test_with_golden_mushroom_and_every_other_patch(self):
        image = _patched(2, GOLDEN.format(2), DUPLICATION.format(2))
        self.assertEqual(self._mushroom(image, 0x32, True)[:2], ([100], 1), "the golden kind, read from the hands")
        image = _image(2, tuple(_others(2) + [ROW.format(2)]))
        self.assertEqual(self._mushroom(image, 0x31, True)[:2], ([35], 1))

    def test_collectible_counts_once_dropped_or_delivered(self):
        piece = 0x1E + 5                                   # carried value of piece 5 (a butterfly)
        everything = _image(2, tuple(_others(2) + [ROW.format(2)]))
        for image, patched in ((_image(2), False), (_patched(2), True), (everything, True)):
            for interrupted in (True, False):
                for owned in (False, True):
                    with self.subTest(patched=patched, interrupted=interrupted, owned=owned):
                        m = _vv2(image, 5)                 # the map's item 5: carried as 0x1E + 5
                        m.mu.mem_write(STATE + piece + 0x2E702, bytes([1 if owned else 0]))
                        m.call(VV2["collectible"], MGR, SLOT)
                        steps = [(a[1], a[-1]) for a in m.args(VV2["queue"])]
                        carry = steps.index((0xF, piece))
                        self.assertEqual(steps.count((0x11, 0x29)), 1, "one award step")
                        self.assertEqual(steps.index((0x11, 0x29)) == carry + 1, patched)
                        _vv2_play(m, interrupted)
                        credited = not (interrupted and not patched)
                        found = m.mu.mem_read(STATE + piece + 0x2E702, 1)[0]
                        self.assertEqual(found, 1 if (credited or owned) else 0)
                        self.assertEqual(len(m.args(VV2["tech"])), 1 if (credited and owned) else 0)


# ---------------------------------------------------------------------------------------------------------------
# A New Home: the mushroom job's queue, played with the real callback dispatcher.
# ---------------------------------------------------------------------------------------------------------------
VV1 = dict(job=0x444500, queue=0x4399F0, dispatch=0x43A230, food=0x41D140, found=0x9E30, kind=0xACB0,
           stubs={0x439470: 4, 0x433970: 4, 0x44B23D: 0, 0x43DEF0: 4, 0x416380: 0, 0x41C960: 8})
ARRAY = HEAP
VV1_MGR = HEAP + 0x1000000


def _vv1(image: bytes, kind: int) -> Machine:
    m = Machine(image)
    m.wr(ARRAY + 0x3E010, VV1_MGR)
    m.wr(ARRAY + 0x3E02C, ARRAY + 0x3F000)
    m.wr(ARRAY + 0x3E024, ARRAY + 0x3F100)
    m.wr(VV1_MGR + VV1["kind"], kind)
    m.stub(VV1["queue"], 0x1C)
    m.stub(0x402F10, 0, 1)
    for addr, pop in VV1["stubs"].items():
        m.stub(addr, pop)
    m.stub(VV1["food"], 4)
    return m


def _vv1_run(image: bytes, kind: int, interrupted: bool) -> tuple[list, int, list, int]:
    m = _vv1(image, kind)
    m.call(VV1["job"], ARRAY, SLOT)
    steps = [(a[1], a[-1]) for a in m.args(VV1["queue"])]
    for step, arg in steps:
        if step == 3 and interrupted:
            break
        if step == 0xE:
            m.call(VV1["dispatch"], ARRAY, SLOT, arg)
    return [a[0] for a in m.args(VV1["food"])], m.rd(VV1_MGR + VV1["found"]), steps, m.rd(VV1_MGR + 0xACAC)


@NEEDS
class NewHomeTests(unittest.TestCase):
    def test_the_job_queues_the_pick_and_no_end_of_trip_award(self):
        for kind, award in ((0, 0x20), (1, 0x21)):
            with self.subTest(kind=kind):
                stock = _vv1_run(_image(1), kind, False)[2]
                patched = _vv1_run(_patched(1), kind, False)[2]
                self.assertIn((0xE, 0x2A), stock)
                self.assertIn((0xE, award), stock)
                self.assertEqual([s for s in stock if s != (0xE, award)], patched, "only the award step is gone")

    def test_mushroom_counts_once_at_the_pick(self):
        for mode in MODES:
            for kind, food in ((0, 8), (1, 45)):
                for interrupted in (True, False):
                    with self.subTest(mode=mode, kind=kind, interrupted=interrupted):
                        got, found, _, picked = _vv1_run(_patched(1, mode=mode), kind, interrupted)
                        self.assertEqual((got, found, picked), ([food], 1, 1))
                        stock, stock_found, _, _ = _vv1_run(_image(1), kind, interrupted)
                        self.assertEqual((stock, stock_found), ([] if interrupted else [food], 0 if interrupted else 1))

    def test_with_golden_mushroom_and_every_other_patch(self):
        image = _patched(1, GOLDEN.format(1))
        self.assertEqual(_vv1_run(image, 2, True)[:2], ([100], 1))
        self.assertEqual(_vv1_run(image, 0, False)[:2], ([8], 1))
        image = _image(1, tuple(_others(1) + [ROW.format(1)]))
        for kind, food in ((0, 8), (1, 45), (2, 100)):
            with self.subTest(kind=kind):
                self.assertEqual(_vv1_run(image, kind, True)[:2], ([food], 1))


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

    @NEEDS
    def test_stock_bytes(self):
        rows = {p.id: p.raw for p in vfp.load_fun_patches()}
        for game in NAMES:
            data = _exe(game).read_bytes()
            for p in rows[ROW.format(game)]["patches"]:
                off = int(p["offset"], 16)
                with self.subTest(game=game, offset=p["offset"]):
                    self.assertEqual(data[off:off + len(p["before"]) // 2].hex().upper(), p["before"])

    def test_readme_and_guide(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        guides = json.loads((ROOT / "data" / "how_to_use.json").read_text(encoding="utf-8"))
        ids = {i for e in guides["patches"] for i in e["ids"]}
        for game in NAMES:
            self.assertIn(f"`{ROW.format(game)}`", readme)
            self.assertIn(ROW.format(game), ids)


if __name__ == "__main__":
    unittest.main()
