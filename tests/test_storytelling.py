"""Dropping an Adult on a Child Tells a Story (A New Home, The Lost Children).

The owner: "Like VV3-VV5 dropping an adult on a child causes the adult to
tell stories to the child, which trains parenting skill for the adult.
(manual drop only) The child does the action "listening to a story" which
essentially just makes them wait in place."  And: in The Lost Children,
dragging an adult onto a child makes them EMBRACE.

What is pinned here, by RUNNING each game's real drop handler (from just
after its hit test), real step queue, pairing step and partner search, and
(for The Lost Children) its real story routines, in an emulator:

* Why The Lost Children embraces: its drop gives the villager under the
  mouse "Waiting for someone" and the dropped one "Embracing", whose pairing
  step searches AGAIN for a waiting villager around the dropped villager's
  own position, which is the mouse minus (0x19, 0x13).  Drop on the upper or
  left part of a child and that search finds nobody (the "Embracing" label
  stays and nothing happens); drop near another waiting adult and it pairs
  with that one.  Only when the search lands on the same child does the
  game's own storytelling (behind it, 0x44F963..) run.  A New Home has the
  same search, and no story at all.
* With "VVFP Storytelling.dll", wherever the drop lands on the child, the
  child listens and the adult tells a story (The Lost Children: its own
  routines, "Teaching children" from Parenting 50; A New Home: the same steps
  in its own step types, in place, one Breeding practice roll), in the
  game's language, age 0 and head/body 0 included.
* Every other drop runs exactly as without it: adult on adult, a teenager or
  child dropped on anyone, a dead child -- on the stock images and on every
  population mode's render with the whole public catalog.
* The rows, the startup loader's list, the bundling and the README.
"""
from __future__ import annotations

import functools
import hashlib
import json
import struct
import sys
import unittest
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as patcher  # noqa: E402

try:  # optional dependency
    import capstone
    import pefile
    from unicorn import (UC_ARCH_X86, UC_HOOK_CODE, UC_HOOK_MEM_FETCH_UNMAPPED,
                         UC_HOOK_MEM_READ_UNMAPPED, UC_HOOK_MEM_WRITE_UNMAPPED, UC_MODE_32, Uc,
                         UcError)
    from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX,
                                   UC_X86_REG_ECX, UC_X86_REG_EDI,
                                   UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP)
    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

GAMES = ("vv1", "vv2")
STOCK = {
    "vv1": ROOT / "research" / "stock-executables" / "Virtual Villagers - A New Home.exe",
    "vv2": ROOT / "research" / "stock-executables" / "Virtual Villagers - The Lost Children.exe",
}
DLL = ROOT / "assets" / "storytelling" / "VVFP Storytelling.dll"
TEST_DLL = ROOT / "tests" / "test_dlls" / "VVFP Storytelling.test.dll"
SOURCE = ROOT / "native" / "vvfp_storytelling" / "vvfp_storytelling.c"
TEST_BUILD_ABSENT = "test builds are not in the release source archive (tests/test_dlls)"
NO_STOCK = "stock executables are not in this checkout"
MODES = ("stock", "collection_progression", "immediate_fixed")

SITES = {
    "vv1": (0x425291, bytes.fromhex("8B4E2057E816020200")),
    "vv2": (0x430F2D, bytes.fromhex("8B4E2053E86A830100")),
}
# The routines a story calls, as the companion verifies them.
VERIFIED = {
    "vv1": {0x439470: "8B44240469C0D803", 0x4399F0: "83EC188B4424208B", 0x43DEF0: "8B4424048BD069D2",
            0x433970: "8B4904E908FFFFFF", 0x402F10: "568B74240885F67E"},
    "vv2": {0x4492A0: "8B44240469C08CE4", 0x44A0E0: "5356578B7C24108B", 0x449F40: "5356578B7C24108B",
            0x44A4E0: "83EC0C53555633C0", 0x4257A0: "33C08D917C040300", 0x4031A0: "568B74240885F67E"},
}

IMAGE_BASE = 0x400000
ARRAY = 0x20000000
ARRAY_SIZE = 0x01000000
STATE = 0x21000000
SCENE = 0x21100000
STRINGS = 0x21200000
STACK = 0x30000000
STACK_SIZE = 0x100000
SENTINEL = 0x3F000000

LISTEN = {0: b"Listening to a story", 1: b"H\xf6rt eine Geschichte zu",
          2: b"Escucha un cuento", 3: b"\xc9coute une histoire"}
TELLING = {0: b"Telling a story", 1: b"Erz\xe4hlt eine Geschichte",
           2: b"Cuenta un cuento", 3: b"Raconte une histoire"}


@dataclass(frozen=True)
class Villager:
    age: int
    male: bool = True
    health: int = 100
    skill: int = 30
    head: int = 3
    body: int = 2


@dataclass(frozen=True)
class Layout:
    stride: int
    state_at: int          # array + this = village state pointer
    strings_at: int        # array + this = string object pointer
    held_at: int           # state + this = the held villager's index
    start: int             # the drop handler, just after its hit test (target in edi / ebx)
    stop: int              # the end of its villager-on-villager case
    rng: int
    real: frozenset        # game routines the route runs for real
    messages: frozenset    # refusal-reason routines (recorded)
    writer: int            # the conception writer (recorded)
    sprintf: int           # the C runtime's sprintf the labels go through (done here)
    active: int
    label: int
    selected: int
    health: int
    age: int
    sex: int
    sick: int
    skill: int
    head: int
    body: int
    queue: int             # first step entry


LAYOUTS = {
    "vv1": Layout(
        stride=0x3D8, state_at=0x3E010, strings_at=0x3E02C, held_at=0xAD34,
        start=0x425241, stop=0x4252BE, rng=0x402F10,
        real=frozenset({0x439470, 0x4454B0, 0x445510, 0x4399F0, 0x43DEF0, 0x43DAD0,
                        0x433970, 0x43D440, 0x439350}),
        messages=frozenset({0x43A130}), writer=0x43BBC0, sprintf=0x44B23D,
        active=0x28, label=0x314, selected=0x29, health=0x344, age=0x348, sex=0x350, sick=0x354,
        skill=0x3BC, head=0x360, body=0x364, queue=0x44,
    ),
    "vv2": Layout(
        stride=0xE48C, state_at=0xE574D4, strings_at=0xE574F0, held_at=0x304F0,
        start=0x430E5B, stop=0x430F63, rng=0x4031A0,
        real=frozenset({0x4492A0, 0x45D4B0, 0x45D510, 0x449B70, 0x44FBB0, 0x44F610,
                        0x441680, 0x44E170, 0x449F40, 0x44A0E0, 0x44A4E0, 0x449160}),
        messages=frozenset({0x44B2A0}), writer=0x44B980, sprintf=0x4682BD,
        active=0x30, label=0x4FC, selected=0x31, health=0x52C, age=0x530, sex=0x538, sick=0x53C,
        skill=0x7E4, head=0x548, body=0x54C, queue=0x4C,
    ),
}
TELLER, CHILD, BYSTANDER = 3, 0, 5   # villager indices: index 0 is a real villager
CHILD_POS = (400, 300)
# Where the mouse is, relative to the child's position, at the drop.  The
# hit test takes the child for any mouse point in [-10, 80] x [-30, 35]; the
# dragged villager sits at the mouse minus (0x19, 0x13).
OVER_THE_CHILD = (35, 25)     # the pairing step's own search finds the child too
ON_ITS_HEAD = (5, -20)        # ...finds nobody: the dropped villager is too far up and left


@dataclass
class Run:
    labels: dict
    queues: dict
    messages: list
    rng_calls: list
    conceived: bool
    regs: dict
    returned: bool


@functools.lru_cache(maxsize=None)
def _stock_bytes(game: str) -> bytes:
    return STOCK[game].read_bytes()


@functools.lru_cache(maxsize=None)
def _mapped(image: bytes) -> bytes:
    return bytes(pefile.PE(data=image, fast_load=True).get_memory_mapped_image())


@functools.lru_cache(maxsize=None)
def _test_dll():
    pe = pefile.PE(str(TEST_DLL))
    exports = {e.name.decode(): pe.OPTIONAL_HEADER.ImageBase + e.address
               for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name}
    return pe.OPTIONAL_HEADER.ImageBase, bytes(pe.get_memory_mapped_image()), exports


@functools.lru_cache(maxsize=None)
def _probe(game: str):
    """Run the test build's probe export: (site, stock bytes, patched bytes, stub)."""
    base, image, exports = _test_dll()
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    mu.mem_map(base, (len(image) + 0xFFFF) & ~0xFFFF)
    mu.mem_write(base, image)
    mu.mem_map(STACK, STACK_SIZE)
    mu.mem_map(SENTINEL, 0x1000)
    buf, esp = STACK + 0x8000, STACK + 0x4000
    mu.mem_write(esp, struct.pack("<6I", SENTINEL, int(game[-1]), buf, buf + 0x20, buf + 0x40, buf + 0x60))
    mu.reg_write(UC_X86_REG_ESP, esp)
    mu.emu_start(exports["VvfpStorytellingProbe"], SENTINEL)
    site, = struct.unpack("<I", mu.mem_read(buf, 4))
    stub, = struct.unpack("<I", mu.mem_read(buf + 0x60, 4))
    return site, bytes(mu.mem_read(buf + 0x20, 9)), bytes(mu.mem_read(buf + 0x40, 9)), stub


@functools.lru_cache(maxsize=None)
def _arg_bytes(mapped: bytes, target: int) -> int:
    """The callee's `ret N` on its fall-through path (following jumps)."""
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    address, seen = target, set()
    while address not in seen:
        seen.add(address)
        offset = address - IMAGE_BASE
        for ins in md.disasm(mapped[offset:offset + 0x4000], address):
            if ins.mnemonic == "ret":
                return int(ins.op_str, 16) if ins.op_str else 0
            if ins.mnemonic == "jmp" and ins.op_str.startswith("0x"):
                address = int(ins.op_str, 16)
                break
        else:
            break
    raise AssertionError(f"no ret for {target:#x}")


def drop(game: str, image: bytes, teller: Villager, child: Villager, *, companion: bool,
         mouse=OVER_THE_CHILD, language: int = 0, rng: dict | None = None,
         bystander: Villager | None = None, entry_point: str = "drop") -> Run:
    """The player drops `teller` (index TELLER) with the mouse at `mouse` from
    `child` (index CHILD), the villager the hit test found there."""
    lay = LAYOUTS[game]
    mapped = _mapped(image)
    size = (len(mapped) + 0xFFFF) & ~0xFFFF
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    mu.mem_map(IMAGE_BASE, size)
    mu.mem_write(IMAGE_BASE, mapped)
    for base, length in ((ARRAY, ARRAY_SIZE), (STATE, 0x100000), (SCENE, 0x100000),
                         (STRINGS, 0x100000), (STACK, STACK_SIZE), (SENTINEL, 0x1000)):
        mu.mem_map(base, length)
    dll_base = dll_end = 0
    if companion:
        base, dll_image, _ = _test_dll()
        dll_base, dll_end = base, base + ((len(dll_image) + 0xFFFF) & ~0xFFFF)
        mu.mem_map(dll_base, dll_end - dll_base)
        mu.mem_write(dll_base, dll_image)
        site, stock, patched, _ = _probe(game)
        assert bytes(mu.mem_read(site, len(stock))) == stock
        mu.mem_write(site, patched)

    def w32(addr, value):
        mu.mem_write(addr, struct.pack("<I", value & 0xFFFFFFFF))

    def r32(addr):
        return struct.unpack("<I", bytes(mu.mem_read(addr, 4)))[0]

    w32(ARRAY + lay.state_at, STATE)
    w32(ARRAY + lay.strings_at, STRINGS)
    w32(STRINGS + 4, STRINGS + 0x100)
    w32(STRINGS + 0x100, language)
    w32(STATE + (0xA2EC if game == "vv1" else 0x2EAA4), 5000)          # food
    w32(STATE + (0xA2DC if game == "vv1" else 0x2EA8C), 1)             # Fertility / Medicine
    # The demo-era population-7 flag, which every created game sets to 1.
    mu.mem_write(STATE + (0x30380 if game == "vv2" else 0xABEC), b"\x01")
    w32(SCENE + 0x20, ARRAY)
    w32(SCENE + 0x10, STATE)
    w32(STATE + lay.held_at, TELLER)
    if game == "vv2":
        w32(SCENE + 0x1E4, TELLER)
    cx, cy = CHILD_POS
    people = [(TELLER, teller, (cx + mouse[0] - 0x19, cy + mouse[1] - 0x13)), (CHILD, child, (cx, cy))]
    if bystander is not None:
        people.append((BYSTANDER, bystander, (cx + 10, cy + 5)))
    for index, v, (x, y) in people:
        rec = ARRAY + index * lay.stride
        mu.mem_write(rec + lay.active, b"\x01")
        w32(rec + 4, x)
        w32(rec + 8, y)
        w32(rec + lay.age, v.age)
        w32(rec + lay.sex, 1 if v.male else 2)
        w32(rec + lay.health, v.health)
        w32(rec + lay.sick, 0)
        w32(rec + lay.skill, v.skill)
        w32(rec + lay.head, v.head)
        w32(rec + lay.body, v.body)
        mu.mem_write(rec + lay.label, b"stale label\0")
    mu.mem_write(ARRAY + TELLER * lay.stride + lay.selected, b"\x01")
    if bystander is not None:                     # standing about: its current step is a wait
        w32(ARRAY + BYSTANDER * lay.stride + lay.queue, 2)

    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    queues = {k: list(v) for k, v in (rng or {}).items()}
    run = Run({}, {}, [], [], False, {}, False)
    pending = []
    faults = []

    def stub_return(uc, address, value):
        esp = uc.reg_read(UC_X86_REG_ESP)
        uc.reg_write(UC_X86_REG_EAX, value)
        uc.reg_write(UC_X86_REG_ESP, esp + 4 + _arg_bytes(mapped, address))
        uc.reg_write(UC_X86_REG_EIP, r32(esp))

    def on_code(uc, address, _size, _):
        if pending:
            pending.pop()
            in_game = IMAGE_BASE <= address < IMAGE_BASE + size
            if in_game and address not in lay.real:
                esp = uc.reg_read(UC_X86_REG_ESP)
                if address == lay.sprintf:          # the label's text: (buffer, text), no %
                    text = bytes(uc.mem_read(r32(esp + 8), 0x40)).split(b"\0")[0]
                    uc.mem_write(r32(esp + 4), text + b"\0")
                    stub_return(uc, address, len(text))
                    return
                if address == lay.rng:
                    limit = r32(esp + 4)
                    run.rng_calls.append(limit)
                    queue = queues.get(limit)
                    stub_return(uc, address, queue.pop(0) if queue else 0)
                    return
                if address in lay.messages:
                    run.messages.append(r32(esp + 4))
                if address == lay.writer:
                    run.conceived = True
                value = 5 if address in (0x425860, 0x41CF90) else 0       # population
                stub_return(uc, address, value)
                return
            if not in_game and not (dll_base <= address < dll_end):
                faults.append(f"call to {address:#x}")
                uc.emu_stop()
                return
        ins = next(md.disasm(bytes(uc.mem_read(address, 16)), address), None)
        if ins is not None and ins.mnemonic == "call":
            pending.append(address + ins.size)

    mu.hook_add(UC_HOOK_CODE, on_code)

    def on_unmapped(uc, access, address, sz, value, _):
        faults.append(f"unmapped {address:#x} at {uc.reg_read(UC_X86_REG_EIP):#x}")
        return False

    mu.hook_add(UC_HOOK_MEM_READ_UNMAPPED | UC_HOOK_MEM_WRITE_UNMAPPED | UC_HOOK_MEM_FETCH_UNMAPPED,
                on_unmapped)

    esp = STACK + STACK_SIZE // 2
    regs = {UC_X86_REG_ESI: SCENE, UC_X86_REG_EBP: 0x6666, UC_X86_REG_ESP: esp}
    if entry_point == "pairing":
        # The embrace queue itself (0x445510 / 0x45D510) from anywhere but the
        # drop handler, as autonomous pairing calls it.
        w32(esp, SENTINEL)
        w32(esp + 4, TELLER)
        regs[UC_X86_REG_ECX] = ARRAY
        start, stop = (0x445510 if game == "vv1" else 0x45D510), SENTINEL
        w32(ARRAY + CHILD * lay.stride + lay.queue, 2)     # the partner waits
    elif game == "vv1":
        regs[UC_X86_REG_EDI] = CHILD
        regs[UC_X86_REG_EBX] = 0x5555
        start, stop = lay.start, lay.stop
    else:
        regs[UC_X86_REG_EBX] = CHILD
        regs[UC_X86_REG_EDI] = 0x7777
        start, stop = lay.start, lay.stop
    for reg, value in regs.items():
        mu.reg_write(reg, value)
    try:
        mu.emu_start(start, stop, count=3_000_000)
    except UcError as exc:
        faults.append(f"{exc} at {mu.reg_read(UC_X86_REG_EIP):#x}")
    if faults:
        raise AssertionError("; ".join(faults))
    run.returned = mu.reg_read(UC_X86_REG_EIP) == stop
    run.regs = {"esi": mu.reg_read(UC_X86_REG_ESI), "ebp": mu.reg_read(UC_X86_REG_EBP),
                "esp": mu.reg_read(UC_X86_REG_ESP)}
    for index in (TELLER, CHILD, BYSTANDER):
        rec = ARRAY + index * lay.stride
        raw = bytes(mu.mem_read(rec + lay.label, 0x30))
        run.labels[index] = raw[:raw.index(b"\0")]
        steps = []
        for k in range(30):
            entry = struct.unpack("<6I", bytes(mu.mem_read(rec + lay.queue + k * 0x18, 0x18)))
            if entry[0] == 0:
                break
            steps.append(entry)
        run.queues[index] = steps
    return run


ADULT = Villager(age=400)
WOMAN = Villager(age=400, male=False)
CHILD_10 = Villager(age=200)
NEWBORN_0 = Villager(age=0, head=0, body=0)            # the owner: 0 is a real age, head and body
TEEN_16 = Villager(age=320)
JUST_18 = Villager(age=360)
JUST_UNDER_18 = Villager(age=359)
DEAD_CHILD = Villager(age=200, health=0)
TEACHER = Villager(age=400, skill=50)

# A New Home: rand(10) -> 4 then 6 (child), rand(8) -> 5 then 2, rand(3) -> 1, rand(5) -> 3.
STORY_RNG = {10: [4, 6], 8: [5, 2], 3: [1], 5: [3]}
# Step entry: (type, a, b, c, 0, d); c is the duration for steps 2 and 7.
V1_CHILD = [(2, 0, 0, 14, 0, 0), (2, 0, 0, 19, 0, 0)]
V1_TELLER = [(15, 3, 3, 0, 0, 0), (2, 0, 0, 3, 0, 0), (7, 0, 0, 8, 0, 0), (15, 3, 0, 0, 0, 0),
             (2, 0, 0, 4, 0, 0), (6, 0, 0, 0, 0, 2), (7, 0, 0, 5, 0, 0), (2, 0, 0, 6, 0, 0)]


@functools.lru_cache(maxsize=None)
def _builds():
    return {build.id: build for build in patcher.load_builds()}


@functools.lru_cache(maxsize=None)
def _render(game: str, mode: str) -> bytes:
    ids = [p.id for p in patcher.load_public_fun_patches() if p.game_id == game]
    data, _ = patcher.render_patched_bytes(STOCK[game], _builds()[game], mode, ids)
    return bytes(data)


def _skip_reason():
    if not HAVE_EMULATOR:
        return "unicorn/capstone/pefile not installed"
    if not all(path.is_file() for path in STOCK.values()):
        return NO_STOCK
    if not TEST_DLL.is_file():
        return TEST_BUILD_ABSENT
    return None


SKIP = _skip_reason()


class StockTests(unittest.TestCase):
    @unittest.skipUnless(all(p.is_file() for p in STOCK.values()), NO_STOCK)
    def test_the_sites_and_every_routine_a_story_calls_are_stock(self):
        for game in GAMES:
            data = _stock_bytes(game)
            site, stock = SITES[game]
            self.assertEqual(data[site - IMAGE_BASE:site - IMAGE_BASE + 9], stock, game)
            for va, hexes in VERIFIED[game].items():
                expected = bytes.fromhex(hexes)
                self.assertEqual(data[va - IMAGE_BASE:va - IMAGE_BASE + 8], expected, f"{game} {va:#x}")

    @unittest.skipUnless(STOCK["vv1"].is_file(), NO_STOCK)
    def test_a_new_home_has_telling_a_story_but_not_listening(self):
        data = _stock_bytes("vv1")
        table = {}
        for i in range(0x275):
            sid, en, *_ = struct.unpack_from("<5I", data, 0x487208 - IMAGE_BASE + i * 20)
            table[sid] = en
        text = lambda sid: data[table[sid] - IMAGE_BASE:data.index(b"\0", table[sid] - IMAGE_BASE)]
        self.assertEqual(text(0xA7), b"Telling a story")
        self.assertEqual(text(0xCC), b"Embracing")
        self.assertNotIn(b"Listening to a story", data)

    @unittest.skipUnless(STOCK["vv2"].is_file(), NO_STOCK)
    def test_the_lost_children_has_its_own_story_words(self):
        data = _stock_bytes("vv2")
        for text in (b"Telling a story\0", b"Listening to a story\0", b"Teaching children\0"):
            self.assertIn(text, data)


@unittest.skipIf(SKIP is not None, str(SKIP))
class WhyTheLostChildrenEmbracesTests(unittest.TestCase):
    """Stock: the pairing step's second search decides, not the player."""

    def test_dropped_on_the_childs_head_it_just_embraces(self):
        run = drop("vv2", _stock_bytes("vv2"), ADULT, CHILD_10, companion=False, mouse=ON_ITS_HEAD)
        self.assertTrue(run.returned)
        self.assertEqual(run.labels[TELLER], b"Embracing")
        self.assertEqual(run.labels[CHILD], b"Waiting for someone")

    def test_another_waiting_adult_nearby_is_embraced_instead(self):
        run = drop("vv2", _stock_bytes("vv2"), ADULT, CHILD_10, companion=False, bystander=WOMAN)
        self.assertEqual(run.labels[TELLER], b"Embracing")
        self.assertNotEqual(run.labels[CHILD], b"Listening to a story")

    def test_only_a_drop_the_search_agrees_with_tells_a_story(self):
        run = drop("vv2", _stock_bytes("vv2"), ADULT, CHILD_10, companion=False)
        self.assertEqual(run.labels[TELLER], b"Telling a story")
        self.assertEqual(run.labels[CHILD], b"Listening to a story")

    def test_a_new_home_has_the_same_search(self):
        run = drop("vv1", _stock_bytes("vv1"), ADULT, CHILD_10, companion=False, mouse=ON_ITS_HEAD)
        self.assertEqual(run.labels[TELLER], b"Embracing")
        self.assertEqual(run.messages, [], "found nobody: not even a refusal")


@unittest.skipIf(SKIP is not None, str(SKIP))
class CompanionTests(unittest.TestCase):

    def test_each_site_jmp_lands_on_its_stub(self):
        for game in GAMES:
            site, stock, patched, stub = _probe(game)
            self.assertEqual((site, stock), SITES[game])
            self.assertEqual(patched[0], 0xE9)
            rel, = struct.unpack("<i", patched[1:5])
            self.assertEqual((site + 5 + rel) & 0xFFFFFFFF, stub)
            self.assertEqual(patched[5:], b"\x90" * 4)

    def _story(self, game, teller, child, **kw):
        run = drop(game, _stock_bytes(game), teller, child, companion=True, rng=dict(STORY_RNG), **kw)
        self.assertTrue(run.returned, "the drop handler went on after its villager case")
        # The handler's own registers survive (The Lost Children's case loads
        # ebp with 360 before the site, A New Home's leaves it alone).
        self.assertEqual(run.regs, {"esi": SCENE, "ebp": 0x6666 if game == "vv1" else 360,
                                    "esp": STACK + STACK_SIZE // 2})
        self.assertEqual(run.messages, [], "no refusal reason")
        self.assertFalse(run.conceived)
        return run

    def assert_vv1_story(self, run, language=0):
        self.assertEqual(run.labels[TELLER], TELLING[language], "the game's own string 0xA7")
        self.assertEqual(run.labels[CHILD], LISTEN[language])
        self.assertEqual(run.queues[CHILD], V1_CHILD)
        self.assertEqual(run.queues[TELLER], V1_TELLER)

    def test_a_new_home_wherever_the_drop_lands(self):
        for mouse in (OVER_THE_CHILD, ON_ITS_HEAD):
            with self.subTest(mouse=mouse):
                self.assert_vv1_story(self._story("vv1", ADULT, CHILD_10, mouse=mouse))

    def test_a_new_home_with_a_waiting_adult_nearby(self):
        run = self._story("vv1", ADULT, CHILD_10, bystander=WOMAN)
        self.assert_vv1_story(run)
        self.assertEqual(run.labels[BYSTANDER], b"stale label", "the bystander is left alone")

    def test_a_new_home_women_age_0_and_the_limits(self):
        for teller, child in ((WOMAN, CHILD_10), (ADULT, NEWBORN_0), (JUST_18, JUST_UNDER_18)):
            with self.subTest(teller=teller, child=child):
                self.assert_vv1_story(self._story("vv1", teller, child))

    def test_a_new_home_follows_the_games_language(self):
        for language in (1, 2, 3):
            with self.subTest(language=language):
                self.assert_vv1_story(self._story("vv1", ADULT, CHILD_10, language=language), language)

    def _stock_story(self, teller):
        """What The Lost Children's own storytelling queues for this pair."""
        return drop("vv2", _stock_bytes("vv2"), teller, CHILD_10, companion=False, rng=dict(STORY_RNG))

    def test_the_lost_children_wherever_the_drop_lands(self):
        own = self._stock_story(ADULT)
        self.assertEqual(own.labels[TELLER], b"Telling a story")
        self.assertIn((6, 0, 0, 0, 0, 2), own.queues[TELLER], "one Parenting practice roll")
        for mouse in (OVER_THE_CHILD, ON_ITS_HEAD):
            with self.subTest(mouse=mouse):
                run = self._story("vv2", ADULT, CHILD_10, mouse=mouse)
                self.assertEqual(run.labels[TELLER], b"Telling a story")
                self.assertEqual(run.labels[CHILD], b"Listening to a story")
                self.assertEqual(run.queues[TELLER], own.queues[TELLER], "the game's own story steps")
                self.assertEqual(run.queues[CHILD], own.queues[CHILD], "the game's own listening steps")

    def test_the_lost_children_with_a_waiting_adult_nearby(self):
        run = self._story("vv2", ADULT, CHILD_10, bystander=WOMAN)
        self.assertEqual(run.labels[CHILD], b"Listening to a story")
        self.assertEqual(run.labels[BYSTANDER], b"stale label")

    def test_the_lost_children_age_0_child_and_head_body_0(self):
        run = self._story("vv2", ADULT, NEWBORN_0)
        self.assertEqual(run.labels[CHILD], b"Listening to a story")

    def test_the_lost_children_teaches_from_parenting_50_as_it_always_has(self):
        own = self._stock_story(TEACHER)
        run = self._story("vv2", TEACHER, CHILD_10, mouse=ON_ITS_HEAD)
        self.assertEqual(own.labels[TELLER], b"Teaching children")
        self.assertEqual(run.labels[TELLER], b"Teaching children")
        self.assertEqual(run.queues[TELLER], own.queues[TELLER])

    def _same_as_stock(self, game, teller, child, **kw):
        image = _stock_bytes(game)
        rng = {100: [99, 99, 99], 300: [299], 3: [1]}
        without = drop(game, image, teller, child, companion=False, rng=dict(rng), **kw)
        with_ = drop(game, image, teller, child, companion=True, rng=dict(rng), **kw)
        self.assertEqual((with_.labels, with_.queues, with_.messages, with_.rng_calls, with_.conceived),
                         (without.labels, without.queues, without.messages, without.rng_calls,
                          without.conceived))
        return with_

    def test_every_other_drop_is_unchanged(self):
        for game in GAMES:
            for teller, child in ((ADULT, WOMAN), (ADULT, Villager(age=400)), (TEEN_16, CHILD_10),
                                  (CHILD_10, ADULT), (CHILD_10, CHILD_10), (NEWBORN_0, ADULT),
                                  (ADULT, DEAD_CHILD)):
                with self.subTest(game=game, teller=teller, child=child):
                    run = self._same_as_stock(game, teller, child)
                    self.assertNotEqual(run.labels[TELLER], b"Telling a story")

    def test_the_pairing_step_itself_is_untouched(self):
        # Entered from anywhere but the drop handler (autonomous pairing calls
        # the same queue), each game does exactly what it did before: A New
        # Home refuses, The Lost Children's own pairing step keeps its own rule.
        for game in GAMES:
            with self.subTest(game=game):
                self._same_as_stock(game, ADULT, CHILD_10, entry_point="pairing")
        run = self._same_as_stock("vv1", ADULT, CHILD_10, entry_point="pairing")
        self.assertNotEqual(run.labels[CHILD], LISTEN[0])


@unittest.skipIf(SKIP is not None, str(SKIP))
class EveryModeTests(unittest.TestCase):
    """With each game's whole public catalog (Birth Control, Manual
    Drop-Breeding and the rest), in every population mode."""

    def test_sites_and_routines_survive_every_render(self):
        for game in GAMES:
            for mode in MODES:
                with self.subTest(game=game, mode=mode):
                    mapped = _mapped(_render(game, mode))
                    site, stock = SITES[game]
                    self.assertEqual(mapped[site - IMAGE_BASE:site - IMAGE_BASE + 9], stock)
                    for va, hexes in VERIFIED[game].items():
                        self.assertEqual(mapped[va - IMAGE_BASE:va - IMAGE_BASE + 8], bytes.fromhex(hexes))

    def test_the_story_runs_in_every_mode(self):
        for game in GAMES:
            for mode in MODES:
                with self.subTest(game=game, mode=mode):
                    run = drop(game, _render(game, mode), ADULT, NEWBORN_0, companion=True,
                               mouse=ON_ITS_HEAD, rng=dict(STORY_RNG))
                    self.assertTrue(run.returned)
                    self.assertEqual(run.labels[TELLER], b"Telling a story")
                    self.assertEqual(run.labels[CHILD], b"Listening to a story")
                    if game == "vv1":
                        self.assertEqual(run.queues[TELLER], V1_TELLER)
                        self.assertEqual(run.queues[CHILD], V1_CHILD)

    def test_adult_on_adult_is_unchanged_in_every_mode(self):
        for game in GAMES:
            for mode in MODES:
                with self.subTest(game=game, mode=mode):
                    image = _render(game, mode)
                    rng = {100: [99, 99, 99], 300: [0], 3: [1]}
                    without = drop(game, image, ADULT, WOMAN, companion=False, rng=dict(rng))
                    with_ = drop(game, image, ADULT, WOMAN, companion=True, rng=dict(rng))
                    self.assertEqual((with_.labels, with_.queues, with_.messages, with_.conceived),
                                     (without.labels, without.queues, without.messages, without.conceived))


class RowTests(unittest.TestCase):
    def test_the_rows_pin_the_dll_and_change_no_bytes(self):
        sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
        for game in GAMES:
            manifest = json.loads((ROOT / "data" / f"{game}_storytelling_feature.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["id"], f"{game}_storytelling")
            self.assertEqual(manifest["game_id"], game)
            self.assertEqual(manifest["patches"], [])
            self.assertNotIn("dependencies", manifest)
            self.assertEqual({f["destination"]: f["sha256"].upper() for f in manifest["companion_files"]},
                             {"VVFP Storytelling.dll": sha})
            self.assertIn("**Needs no other patch.**", manifest["description"])
            site, stock = SITES[game]
            self.assertEqual(manifest["runtime_detours"][0]["va"], f"0x{site:06X}")
            self.assertEqual(manifest["runtime_detours"][0]["stock_bytes"], stock.hex().upper())

    def test_started_by_the_startup_loader(self):
        self.assertIn("VVFP Storytelling.dll", patcher.STARTUP_LOADER_COMPANIONS)
        header = (ROOT / "native" / "shared" / "startup_companions.h").read_text(encoding="utf-8")
        self.assertIn('"VVFP Storytelling.dll",', header)
        self.assertIn("void __stdcall VvfpStartup(int game, unsigned int shipped)",
                      SOURCE.read_text(encoding="utf-8"))
        self.assertIn(b"VVFP Storytelling.dll", (ROOT / "assets" / "startup" / "VVFP Startup.dll").read_bytes())
        records = {p.id: p for p in patcher.load_fun_patches()}
        bit = 1 << (patcher.STARTUP_LOADER_COMPANIONS.index("VVFP Storytelling.dll") + 1)
        for game in GAMES:
            self.assertEqual(patcher._startup_loader_mask(game, [records[f"{game}_storytelling"]]) & bit, bit)

    def test_on_by_default_and_in_select_all(self):
        from vv_fun_patcher_gui import (default_fun_patch_selection, owners_default_fun_patch_selection,
                                        select_all_fun_patch_selection)
        for game in GAMES:
            self.assertTrue(default_fun_patch_selection(f"{game}_storytelling"))
            self.assertTrue(owners_default_fun_patch_selection(f"{game}_storytelling"))
            self.assertTrue(select_all_fun_patch_selection(f"{game}_storytelling"))

    def test_registered_bundled_documented(self):
        source = (ROOT / "src" / "vv_fun_patcher.py").read_text(encoding="utf-8")
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("assets/storytelling/VVFP Storytelling.dll", release)
        for game in GAMES:
            self.assertIn(f'ROOT / "data" / "{game}_storytelling_feature.json"', source)
            self.assertIn(f"data/{game}_storytelling_feature.json", release)
            self.assertIn(f"- Patch ID: `{game}_storytelling`", readme)


if __name__ == "__main__":
    unittest.main()
