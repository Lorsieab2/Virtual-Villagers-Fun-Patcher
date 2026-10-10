"""Dropping an Adult on a Child Tells a Story (A New Home).

The owner: "Like VV3-VV5 dropping an adult on a child causes the adult to
tell stories to the child, which trains parenting skill for the adult.
(manual drop only) The child does the action "listening to a story" which
essentially just makes them wait in place."  In A New Home it replaces the
embrace (Parenting is "Breeding" there).

What is pinned here:

* Stock A New Home has no story on the drop: the pairing handler 0x43DAD0
  refuses a pair with anyone under 18 and, for the selected villager, shows
  a reason and clears both.  "Telling a story" (0xA7) exists only as one of
  the idle chats (0x446480); "Listening to a story" does not exist.
* Stock The Lost Children ALREADY does what the owner asks, on the same
  refusal path of its pairing handler (0x44F610 -> 0x44A0E0 listener,
  0x449F40 teller with one Parenting practice roll, 0x44A4E0 "Teaching
  children" at Parenting 50+).  Proven here by RUNNING its real drop route on
  the stock executable, so no Lost Children patch is needed.
* The companion, RUN in an emulator together with A New Home's real drop
  route (0x425241 -> 0x4454B0 / 0x445510 -> 0x43DEF0 -> 0x43DAD0), its real
  step queue (0x4399F0, 0x439470, 0x43DEF0 and the step starters) and string
  getter (0x433970), on the stock image and on every population mode's
  render with the whole public A New Home catalog:
    - an 18+ adult dropped on a living child under 18 -- age 0 and head/body
      0 included -- gives the child "Listening to a story" with two standing
      waits, and the adult the game's own "Telling a story" with The Lost
      Children's storyteller steps ending in one Breeding practice roll;
    - the child's label follows the game's language;
    - every other drop (adult on adult, a teenager or a child dropped on a
      child, a child on an adult, a dead child, an unselected villager, any
      entry that is not the player's drop) runs exactly as without it.
* The row, the startup loader's list, the bundling and the README.
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

STOCK = {
    "vv1": ROOT / "research" / "stock-executables" / "Virtual Villagers - A New Home.exe",
    "vv2": ROOT / "research" / "stock-executables" / "Virtual Villagers - The Lost Children.exe",
}
DLL = ROOT / "assets" / "storytelling" / "VVFP VV1 Storytelling.dll"
TEST_DLL = ROOT / "tests" / "test_dlls" / "VVFP VV1 Storytelling.test.dll"
TEST_BUILD_ABSENT = "test builds are not in the release source archive (tests/test_dlls)"
MANIFEST = ROOT / "data" / "vv1_storytelling_feature.json"
NO_STOCK = "stock executables are not in this checkout"
MODES = ("stock", "collection_progression", "immediate_fixed")

SITE = 0x43DDC7
SITE_STOCK = bytes.fromhex("8A452984C00F84B6000000")
# The other bytes the companion verifies before installing.
VERIFIED = {
    0x43DAD0: "83EC0C5355568BF157",                     # the handler's frame
    0x43DEC7: "5F5E4A83E2038955345D5B83C40CC204",     # its epilogue
    0x4252B9: "E852020200",                             # the drop: call 0x445510
    0x445570: "E87B89FFFF",                             # ...which starts step 9 at once
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
    skill: int = 60
    head: int = 3
    body: int = 2


@dataclass(frozen=True)
class Layout:
    stride: int
    state_at: int          # array + this = village state pointer
    strings_at: int        # array + this = string object pointer
    held_at: int           # state + this = the held villager's index (VV1); scene object for VV2
    start: int             # first instruction of the drop route
    stop: int              # its end
    rng: int
    real: frozenset        # game routines the route runs for real
    finder: int            # the handler's partner finder (stubbed: returns the target)
    messages: frozenset    # refusal-reason routines (recorded)
    writer: int            # the conception writer (recorded, stops nothing)
    sprintf: int           # the C runtime's sprintf the labels go through (done here)
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
    entry: int             # entry size


LAYOUTS = {
    "vv1": Layout(
        stride=0x3D8, state_at=0x3E010, strings_at=0x3E02C, held_at=0xAD34,
        start=0x425241, stop=0x4252BE, rng=0x402F10,
        real=frozenset({0x439470, 0x4454B0, 0x445510, 0x4399F0, 0x43DEF0, 0x43DAD0,
                        0x433970, 0x43D440}),
        finder=0x439350, messages=frozenset({0x43A130}), writer=0x43BBC0, sprintf=0x44B23D,
        label=0x314, selected=0x29, health=0x344, age=0x348, sex=0x350, sick=0x354,
        skill=0x3BC, head=0x360, body=0x364, queue=0x44, entry=0x18,
    ),
    "vv2": Layout(
        stride=0xE48C, state_at=0xE574D4, strings_at=0xE574F0, held_at=0x304F0,
        start=0x430E5B, stop=0x430F63, rng=0x4031A0,
        real=frozenset({0x4492A0, 0x45D4B0, 0x45D510, 0x449B70, 0x44FBB0, 0x44F610,
                        0x441680, 0x44E170, 0x449F40, 0x44A0E0, 0x44A4E0}),
        finder=0x449160, messages=frozenset({0x44B2A0}), writer=0x44B980, sprintf=0x4682BD,
        label=0x4FC, selected=0x31, health=0x52C, age=0x530, sex=0x538, sick=0x53C,
        skill=0x7E4, head=0x548, body=0x54C, queue=0x4C, entry=0x18,
    ),
}
TELLER, CHILD = 3, 0       # villager indices: index 0 is a real villager


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
def _probe():
    """Run the test build's probe export: (site, stock bytes, patched bytes, stub)."""
    base, image, exports = _test_dll()
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    mu.mem_map(base, (len(image) + 0xFFFF) & ~0xFFFF)
    mu.mem_write(base, image)
    mu.mem_map(STACK, STACK_SIZE)
    buf, esp = STACK + 0x8000, STACK + 0x4000
    mu.mem_write(esp, struct.pack("<5I", SENTINEL, buf, buf + 0x20, buf + 0x40, buf + 0x60))
    mu.reg_write(UC_X86_REG_ESP, esp)
    mu.mem_map(SENTINEL, 0x1000)
    mu.emu_start(exports["VvfpVv1StorytellingProbe"], SENTINEL)
    site, = struct.unpack("<I", mu.mem_read(buf, 4))
    stub, = struct.unpack("<I", mu.mem_read(buf + 0x60, 4))
    return site, bytes(mu.mem_read(buf + 0x20, 11)), bytes(mu.mem_read(buf + 0x40, 11)), stub


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
         language: int = 0, rng: dict | None = None, selected: bool = True,
         caller_is_the_drop: bool = True) -> Run:
    """The player drops `teller` (index TELLER) on `child` (index CHILD)."""
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
        site, stock, patched, _ = _probe()
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
    for index, v in ((TELLER, teller), (CHILD, child)):
        rec = ARRAY + index * lay.stride
        w32(rec + lay.age, v.age)
        w32(rec + lay.sex, 1 if v.male else 2)
        w32(rec + lay.health, v.health)
        w32(rec + lay.sick, 0)
        w32(rec + lay.skill, v.skill)
        w32(rec + lay.head, v.head)
        w32(rec + lay.body, v.body)
        mu.mem_write(rec + lay.label, b"stale label\0")
    if selected:
        mu.mem_write(ARRAY + TELLER * lay.stride + lay.selected, b"\x01")

    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    queues = {k: list(v) for k, v in (rng or {}).items()}
    run = Run({}, {}, [], [], False, {}, False)
    pending = []
    faults = []

    def stub_return(uc, address, value):
        esp = uc.reg_read(UC_X86_REG_ESP)
        ret = r32(esp)
        uc.reg_write(UC_X86_REG_EAX, value)
        uc.reg_write(UC_X86_REG_ESP, esp + 4 + _arg_bytes(mapped, address))
        uc.reg_write(UC_X86_REG_EIP, ret)

    def on_code(uc, address, size, _):
        if pending:
            pending.pop()
            in_game = IMAGE_BASE <= address < IMAGE_BASE + size_image
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
                value = CHILD if address == lay.finder else 0
                if address == 0x425860 or address == 0x41CF90:
                    value = 5                                   # population
                stub_return(uc, address, value)
                return
            if not in_game and not (dll_base <= address < dll_end):
                faults.append(f"call to {address:#x}")
                uc.emu_stop()
                return
        code = bytes(uc.mem_read(address, 16))
        ins = next(md.disasm(code, address), None)
        if ins is not None and ins.mnemonic == "call":
            pending.append(address + ins.size)

    size_image = size
    mu.hook_add(UC_HOOK_CODE, on_code)

    def on_unmapped(uc, access, address, sz, value, _):
        faults.append(f"unmapped {address:#x} at {uc.reg_read(UC_X86_REG_EIP):#x}")
        return False

    mu.hook_add(UC_HOOK_MEM_READ_UNMAPPED | UC_HOOK_MEM_WRITE_UNMAPPED | UC_HOOK_MEM_FETCH_UNMAPPED,
                on_unmapped)

    esp = STACK + STACK_SIZE // 2
    regs = {UC_X86_REG_ESI: SCENE, UC_X86_REG_EBP: 0x6666, UC_X86_REG_ESP: esp}
    if game == "vv1" and not caller_is_the_drop:
        # The same embrace queue (0x445510) and everything below it, entered
        # from somewhere that is not the player's drop: the handler then finds
        # a sentinel, not 0x4252BE, at [esp+0x30].
        w32(esp, SENTINEL)
        w32(esp + 4, TELLER)
        regs[UC_X86_REG_ECX] = ARRAY
        start, stop = 0x445510, SENTINEL
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
        mu.emu_start(start, stop, count=2_000_000)
    except UcError as exc:
        faults.append(f"{exc} at {mu.reg_read(UC_X86_REG_EIP):#x}")
    if faults:
        raise AssertionError("; ".join(faults))
    run.returned = mu.reg_read(UC_X86_REG_EIP) == stop
    run.regs = {"esi": mu.reg_read(UC_X86_REG_ESI), "ebp": mu.reg_read(UC_X86_REG_EBP),
                "esp": mu.reg_read(UC_X86_REG_ESP)}
    for index in (TELLER, CHILD):
        rec = ARRAY + index * lay.stride
        raw = bytes(mu.mem_read(rec + lay.label, 0x30))
        run.labels[index] = raw[:raw.index(b"\0")]
        steps = []
        for k in range(30):
            entry = struct.unpack("<6I", bytes(mu.mem_read(rec + lay.queue + k * lay.entry, lay.entry)))
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

# Scripted rolls for the story: rand(10) -> 4 then 6 (child), rand(8) -> 5 then 2,
# rand(3) -> 1, rand(5) -> 3 (adult).
STORY_RNG = {10: [4, 6], 8: [5, 2], 3: [1], 5: [3]}
# VV1 step entry: (type, a, b, c, 0, d); c is the duration for steps 2 and 7.
EXPECTED_CHILD = [(2, 0, 0, 14, 0, 0), (2, 0, 0, 19, 0, 0)]
EXPECTED_TELLER = [(15, 3, 3, 0, 0, 0), (2, 0, 0, 3, 0, 0), (7, 0, 0, 8, 0, 0), (15, 3, 0, 0, 0, 0),
                   (2, 0, 0, 4, 0, 0), (6, 0, 0, 0, 0, 2), (7, 0, 0, 5, 0, 0), (2, 0, 0, 6, 0, 0)]


@functools.lru_cache(maxsize=None)
def _builds():
    return {build.id: build for build in patcher.load_builds()}


@functools.lru_cache(maxsize=None)
def _render(mode: str) -> bytes:
    build = _builds()["vv1"]
    ids = [p.id for p in patcher.load_public_fun_patches() if p.game_id == "vv1"]
    data, _ = patcher.render_patched_bytes(STOCK["vv1"], build, mode, ids)
    return bytes(data)


def _skip_reason():
    if not HAVE_EMULATOR:
        return "unicorn/capstone/pefile not installed"
    if not STOCK["vv1"].is_file():
        return NO_STOCK
    if not TEST_DLL.is_file():
        return TEST_BUILD_ABSENT
    return None


class StockTests(unittest.TestCase):
    @unittest.skipUnless(STOCK["vv1"].is_file(), NO_STOCK)
    def test_the_site_and_every_verified_byte_are_stock(self):
        data = _stock_bytes("vv1")
        off = lambda va: va - IMAGE_BASE        # A New Home's sections are file-aligned at their RVAs
        self.assertEqual(data[off(SITE):off(SITE) + 11], SITE_STOCK,
                         "mov al,[ebp+0x29]; test al,al; je 0x43DE88")
        for va, hexes in VERIFIED.items():
            expected = bytes.fromhex(hexes)
            self.assertEqual(data[off(va):off(va) + len(expected)], expected, hex(va))

    @unittest.skipUnless(STOCK["vv1"].is_file(), NO_STOCK)
    def test_a_new_home_has_telling_a_story_but_not_listening(self):
        data = _stock_bytes("vv1")
        table = {}
        for i in range(0x275):
            sid, en, de, es, fr = struct.unpack_from("<5I", data, 0x487208 - IMAGE_BASE + i * 20)
            table[sid] = en
        text = lambda sid: data[table[sid] - IMAGE_BASE:data.index(b"\0", table[sid] - IMAGE_BASE)]
        self.assertEqual(text(0xA7), b"Telling a story")
        self.assertEqual(text(0xCC), b"Embracing")
        self.assertNotIn(b"Listening to a story", data)

    @unittest.skipUnless(STOCK["vv2"].is_file(), NO_STOCK)
    def test_the_lost_children_has_both_and_teaching_children(self):
        data = _stock_bytes("vv2")
        for text in (b"Telling a story\0", b"Listening to a story\0", b"Teaching children\0"):
            self.assertIn(text, data)


@unittest.skipUnless(HAVE_EMULATOR and STOCK["vv2"].is_file(), "emulator or stock executable missing")
class LostChildrenAlreadyTellsStoriesTests(unittest.TestCase):
    """The Lost Children needs no patch: its stock drop already tells a story."""

    def test_adult_on_child_tells_a_story_in_stock(self):
        run = drop("vv2", _stock_bytes("vv2"), Villager(age=400, skill=30), CHILD_10, companion=False,
                   rng={10: [4], 30: [7], 3: [1], 8: [5, 2], 5: [3], 20: [3], 120: [9], 100: [99]})
        self.assertTrue(run.returned)
        self.assertEqual(run.labels[TELLER], b"Telling a story")
        self.assertEqual(run.labels[CHILD], b"Listening to a story")
        self.assertIn((6, 0, 0, 0, 0, 2), [s for s in run.queues[TELLER]], "one Parenting practice roll")
        self.assertFalse(run.conceived)

    def test_age_0_child_listens_in_stock(self):
        run = drop("vv2", _stock_bytes("vv2"), Villager(age=400, skill=30), NEWBORN_0, companion=False)
        self.assertEqual(run.labels[CHILD], b"Listening to a story")

    def test_parenting_50_or_more_teaches_children_instead(self):
        run = drop("vv2", _stock_bytes("vv2"), Villager(age=400, skill=50), CHILD_10, companion=False)
        self.assertEqual(run.labels[TELLER], b"Teaching children")

    def test_a_teenager_on_a_child_gets_no_story_in_stock(self):
        run = drop("vv2", _stock_bytes("vv2"), Villager(age=300, skill=30), CHILD_10, companion=False)
        self.assertNotEqual(run.labels[TELLER], b"Telling a story")
        self.assertNotEqual(run.labels[CHILD], b"Listening to a story")


@unittest.skipIf(_skip_reason() is not None, str(_skip_reason()))
class CompanionTests(unittest.TestCase):

    def test_the_site_jmp_lands_on_the_stub(self):
        site, stock, patched, stub = _probe()
        self.assertEqual(site, SITE)
        self.assertEqual(stock, SITE_STOCK)
        self.assertEqual(patched[0], 0xE9)
        rel, = struct.unpack("<i", patched[1:5])
        self.assertEqual((SITE + 5 + rel) & 0xFFFFFFFF, stub)
        self.assertEqual(patched[5:], b"\x90" * 6)

    def _story(self, image, teller, child, **kw):
        run = drop("vv1", image, teller, child, companion=True, rng=dict(STORY_RNG), **kw)
        self.assertTrue(run.returned, "the drop returned to the input handler")
        self.assertEqual(run.regs["esi"], SCENE, "the input handler's registers survive")
        self.assertEqual(run.regs["ebp"], 0x6666)
        self.assertEqual(run.regs["esp"], STACK + STACK_SIZE // 2)
        return run

    def assert_story(self, run, language=0):
        # The teller's label is the game's own string 0xA7 in the game's language.
        self.assertEqual(run.labels[TELLER], TELLING[language])
        self.assertEqual(run.labels[CHILD], LISTEN[language])
        self.assertEqual(run.queues[CHILD], EXPECTED_CHILD)
        self.assertEqual(run.queues[TELLER], EXPECTED_TELLER)
        self.assertEqual(run.messages, [], "no refusal reason")
        self.assertFalse(run.conceived)

    def test_adult_on_child_tells_a_story(self):
        self.assert_story(self._story(_stock_bytes("vv1"), ADULT, CHILD_10))

    def test_a_woman_tells_stories_too(self):
        self.assert_story(self._story(_stock_bytes("vv1"), WOMAN, CHILD_10))

    def test_an_age_0_child_with_head_and_body_0_listens(self):
        self.assert_story(self._story(_stock_bytes("vv1"), ADULT, NEWBORN_0))

    def test_the_age_limits_are_the_handlers_own(self):
        self.assert_story(self._story(_stock_bytes("vv1"), JUST_18, JUST_UNDER_18))

    def test_the_childs_label_follows_the_games_language(self):
        for language in (1, 2, 3):
            with self.subTest(language=language):
                self.assert_story(self._story(_stock_bytes("vv1"), ADULT, CHILD_10, language=language),
                                  language)

    def _same_as_stock(self, teller, child, **kw):
        image = _stock_bytes("vv1")
        rng = {100: [99, 99, 99], 300: [299], 3: [1]}
        without = drop("vv1", image, teller, child, companion=False, rng=dict(rng), **kw)
        with_ = drop("vv1", image, teller, child, companion=True, rng=dict(rng), **kw)
        self.assertEqual((with_.labels, with_.queues, with_.messages, with_.rng_calls, with_.conceived),
                         (without.labels, without.queues, without.messages, without.rng_calls,
                          without.conceived))
        self.assertNotEqual(with_.labels[TELLER], b"Telling a story")
        self.assertNotIn(LISTEN[0], with_.labels.values())
        return with_

    def test_adult_on_adult_is_unchanged(self):
        self._same_as_stock(ADULT, WOMAN)
        self._same_as_stock(ADULT, Villager(age=400))      # same sex: the stock refusal

    def test_a_teenager_on_a_child_is_unchanged(self):
        run = self._same_as_stock(TEEN_16, CHILD_10)
        self.assertTrue(run.messages, "the stock refusal reason is still shown")

    def test_a_child_on_anyone_is_unchanged(self):
        self._same_as_stock(CHILD_10, ADULT)
        self._same_as_stock(CHILD_10, CHILD_10)
        self._same_as_stock(NEWBORN_0, ADULT)

    def test_a_dead_child_is_unchanged(self):
        self._same_as_stock(ADULT, DEAD_CHILD)

    def test_an_unselected_villager_is_unchanged(self):
        self._same_as_stock(ADULT, CHILD_10, selected=False)


@unittest.skipIf(_skip_reason() is not None, str(_skip_reason()))
class NotTheDropTests(unittest.TestCase):
    """Only the player's drop: the same handler entered from anywhere else
    (the drop's return address is not at [esp+0x30]) keeps the stock result."""

    def test_the_same_handler_entered_elsewhere_keeps_the_stock_refusal(self):
        image = _stock_bytes("vv1")
        for teller, child in ((ADULT, CHILD_10), (ADULT, NEWBORN_0)):
            with self.subTest(child=child):
                without = drop("vv1", image, teller, child, companion=False, caller_is_the_drop=False)
                with_ = drop("vv1", image, teller, child, companion=True, caller_is_the_drop=False)
                self.assertTrue(with_.returned)
                self.assertEqual((with_.labels, with_.queues, with_.messages),
                                 (without.labels, without.queues, without.messages))
                self.assertNotIn(LISTEN[0], with_.labels.values())
                self.assertTrue(with_.messages, "the stock refusal reason")


@unittest.skipIf(_skip_reason() is not None, str(_skip_reason()))
class EveryModeTests(unittest.TestCase):
    """With the whole public A New Home catalog (Birth Control, Manual
    Drop-Breeding and the rest), in every population mode."""

    def test_the_site_and_verified_bytes_survive_every_render(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                mapped = _mapped(_render(mode))
                self.assertEqual(mapped[SITE - IMAGE_BASE:SITE - IMAGE_BASE + 11], SITE_STOCK)
                for va, hexes in VERIFIED.items():
                    expected = bytes.fromhex(hexes)
                    self.assertEqual(mapped[va - IMAGE_BASE:va - IMAGE_BASE + len(expected)], expected,
                                     f"{mode} {va:#x}")

    def test_the_story_runs_in_every_mode(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                image = _render(mode)
                run = drop("vv1", image, ADULT, NEWBORN_0, companion=True, rng=dict(STORY_RNG))
                self.assertTrue(run.returned)
                self.assertEqual(run.labels[TELLER], b"Telling a story")
                self.assertEqual(run.labels[CHILD], LISTEN[0])
                self.assertEqual(run.queues[TELLER], EXPECTED_TELLER)
                self.assertEqual(run.queues[CHILD], EXPECTED_CHILD)

    def test_adult_on_adult_is_unchanged_in_every_mode(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                image = _render(mode)
                rng = {100: [99, 99, 99], 300: [0], 3: [1]}
                without = drop("vv1", image, ADULT, WOMAN, companion=False, rng=dict(rng))
                with_ = drop("vv1", image, ADULT, WOMAN, companion=True, rng=dict(rng))
                self.assertEqual((with_.labels, with_.queues, with_.messages, with_.conceived),
                                 (without.labels, without.queues, without.messages, without.conceived))


class RowTests(unittest.TestCase):
    def test_the_row_pins_the_dll_and_changes_no_bytes(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["id"], "vv1_storytelling")
        self.assertEqual(manifest["game_id"], "vv1")
        self.assertEqual(manifest["patches"], [])
        self.assertNotIn("dependencies", manifest)
        pinned = {f["destination"]: f["sha256"].upper() for f in manifest["companion_files"]}
        self.assertEqual(pinned, {"VVFP VV1 Storytelling.dll":
                                  hashlib.sha256(DLL.read_bytes()).hexdigest().upper()})
        self.assertIn("**Needs no other patch.**", manifest["description"])
        self.assertEqual(manifest["runtime_detours"][0]["va"], "0x43DDC7")
        self.assertEqual(manifest["runtime_detours"][0]["stock_bytes"], SITE_STOCK.hex().upper())

    def test_started_by_the_startup_loader(self):
        self.assertIn("VVFP VV1 Storytelling.dll", patcher.STARTUP_LOADER_COMPANIONS)
        header = (ROOT / "native" / "shared" / "startup_companions.h").read_text(encoding="utf-8")
        self.assertIn('"VVFP VV1 Storytelling.dll",', header)
        source = (ROOT / "native" / "vv1_storytelling" / "vv1_storytelling.c").read_text(encoding="utf-8")
        self.assertIn("void __stdcall VvfpStartup(int game, unsigned int shipped)", source)
        self.assertIn(b"VVFP VV1 Storytelling.dll", (ROOT / "assets" / "startup" / "VVFP Startup.dll").read_bytes())

    def test_every_mode_ships_it_with_its_startup_bit(self):
        records = {p.id: p for p in patcher.load_fun_patches()}
        feature = records["vv1_storytelling"]
        mask = patcher._startup_loader_mask("vv1", [feature])
        bit = 1 << (patcher.STARTUP_LOADER_COMPANIONS.index("VVFP VV1 Storytelling.dll") + 1)
        self.assertEqual(mask & bit, bit)

    def test_on_by_default_and_in_select_all(self):
        from vv_fun_patcher_gui import (default_fun_patch_selection, owners_default_fun_patch_selection,
                                        select_all_fun_patch_selection)
        self.assertTrue(default_fun_patch_selection("vv1_storytelling"))
        self.assertTrue(owners_default_fun_patch_selection("vv1_storytelling"))
        self.assertTrue(select_all_fun_patch_selection("vv1_storytelling"))

    def test_registered_bundled_documented(self):
        source = (ROOT / "src" / "vv_fun_patcher.py").read_text(encoding="utf-8")
        self.assertIn('ROOT / "data" / "vv1_storytelling_feature.json"', source)
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        self.assertIn("assets/storytelling/VVFP VV1 Storytelling.dll", release)
        self.assertIn("data/vv1_storytelling_feature.json", release)
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("- Patch ID: `vv1_storytelling`", readme)


if __name__ == "__main__":
    unittest.main()
