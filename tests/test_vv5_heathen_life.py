"""New Believers: "VVFP Heathen Life.dll" -- the Heathens' own camp life, workstream W-B of Heathen Tribe Expansion and
Evolution (docs/heathen-tribe-expansion-design.md sections 7, 8 and 10; the owner's decisions 8, 9, 10 and 17 in
docs/heathen-tribe-expansion-decisions.md).

EMULATED on the stock New Believers executable (and on the patcher's three population modes' renders): the companion
is started as the start-up chain starts it, then its bridge export VvfpHeathenLifeUnit (which "VVFP Heathen
Aging.dll" calls from its life-tick splice; tested here directly) and the game's own next-action picker from its
faction test 0x46F0BA run on hand-made records.  What runs is the game's code: the step adders (walk to an area
0x4744C0 with the walk picker 0x477B90 over the real walk map lcmap.dat, walk to a point 0x4745A0, gesture 0x474450,
wait 0x4747E0, carry 0x474D80, drop 0x474DE0, animation 0x475160) and the step queue they fill (record +0,
0x58-byte steps, type at +0).  Stood in for: rand 0x403660 (counted: the life unit never draws it), the village
object 0x425950 (difficulty, noni and crops), the string table 0x450D40 / 0x4506D0, the activity stop 0x473440 (clears
the queue, counted), the queue's start 0x473590 (counted), the position 0x466350, and the Heathen AI 0x46E9E0
(counted: the stock branch was taken).
"""
from __future__ import annotations

import itertools
import struct
import sys
import unittest
from pathlib import Path
from typing import ClassVar

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

try:
    from story_emulator import RETURN, STACK_TOP
    from test_companion_installs_all_or_none import (
        HAVE_EMULATOR,
        Machine,
        render,
        stock_path,
        with_requirements,
    )
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

DLL = ROOT / "assets" / "heathen_life" / "VVFP Heathen Life.dll"
SOURCE = ROOT / "native" / "vvfp_heathen_life" / "vvfp_heathen_life.c"
LCMAP = ROOT / "research" / "game-data" / "vv5" / "lcmap.dat"
FLAG = "VVFP Heathen Tribe Evolution.txt"
OPTIONS = "VVFP Heathen Options.txt"

STOCK_MANAGER, STOCK_SLOTS = 0x554148, 150
BIG_MANAGER, BIG_SLOTS = 0x800000, 256
STRIDE = 0x2F44
AGE, SEX, NAME, HEALTH, CAUSE, SICK, PREGNANT, SKILLS = 0x1B8C, 0x1B90, 0x1B9C, 0x1C40, 0x1C44, 0x1C48, 0x1C4C, 0x1C5C
PRESENT, HELD, FACTION, ROLE, BEHAVIOUR, DOING, LIKES, DISLIKES = (
    0x1CD4, 0x1CD6, 0x1CEC, 0x1CFC, 0x1D10, 0x1D14, 0x1F5C, 0x1F68)
FARMING, PARENTING, HEALING, RESEARCH, BUILDING, DEVOTION = range(6)
LEARNING = 0x27
MEDICINE, FOOD, PEOPLE_CURED = 0x51D5D0, 0x51D34C, 0x51D368
WEATHER, MAP = 0x718EA0, 0x718EE8
PUZZLE_PROGRESS, PUZZLE_NEEDED = 0x51E008, 0x51DF30
SITE_OBJECTS = {3: 0x51DAB0, 4: 0x51DB40, 5: 0x51DC50}     # 0x4CBDC0: CClothingHut, CLoveShack, CNurseryHut
GAME_OBJECT = 0x30000000
DIFFICULTY, NONI, CROPS = 0x17D54, 0x17D58, 0x17D5C
PICK_SITE, PICK_FRAME = 0x46F0BA, 0x10
RAND, GAME, TEXTS, TEXT, STOP, START, POSITION, HEATHEN_AI = (
    0x403660, 0x425950, 0x450D40, 0x4506D0, 0x473440, 0x473590, 0x466350, 0x46E9E0)
TEACHER = 0x43A810
CURE_BEGIN, CURE_COUNT = 0x468C3C, 0x468D4D
STEP, STEPS = 0x58, 0x50
HE_LIFE_IDLE, HE_LIFE_UNIT, HE_LIFE_ROW, KEEP_SICK, HANDLED = 0, 1, 0x100, 1, 2
CAMP, NONI_AREA, CROP_AREA, LAKE, POOLS, STATUE, LAB = 0x39, 0x1A, 0x52, 0x69, 0x7C, 0x45, 0x0E
# Step types the believers' scripts use that do the work: the skill check (0x474780) and the payoff (0x474EF0).
SKILL_CHECK_STEP, PAYOFF_STEP = 0x0A, 0x14


def _areas() -> dict[int, tuple[int, int, int, int]]:
    """Each walk area's box in pixels (cell >> 4 & 0x7FF, 8 px cells), from the real lcmap.dat."""
    cells = struct.unpack("<102400I", LCMAP.read_bytes())
    box: dict[int, list[int]] = {}
    for i, cell in enumerate(cells):
        area = (cell >> 4) & 0x7FF
        x, y = (i % 320) * 8, (i // 320) * 8
        b = box.setdefault(area, [x, y, x, y])
        b[0], b[1], b[2], b[3] = min(b[0], x), min(b[1], y), max(b[2], x), max(b[3], y)
    return {a: tuple(b) for a, b in box.items()}


class Camp(Machine):
    """The stock game (or a rendered mode) with the companion started and the real walk map loaded."""

    def __init__(self, *, row: bool = True, options: str | None = None, exe: bytes | None = None,
                 spoil_site: bool = False):
        exe = bytearray(exe if exe is not None else stock_path(5).read_bytes())
        if spoil_site:
            # Another patch's bytes at the picker's faction test: the companion must install nothing.
            exe[self._file_offset(bytes(exe), PICK_SITE)] ^= 0xFF
        super().__init__(bytes(exe), DLL, present=(FLAG,) if row else ())
        self.options = options
        self.rand_calls = 0
        self.stopped: list[int] = []
        self.started: list[int] = []
        self.stock_ai: list[int] = []
        self.positions: dict[int, tuple[int, int]] = {}
        self.files: dict[int, list] = {}
        self.api_handlers["GetCurrentProcessId"] = lambda p: (0x1234, 0)
        # The game itself for NULL; no other companion is loaded.
        self.api_handlers["GetModuleHandleA"] = lambda p: ((0x400000 if p.arg(0) == 0 else 0), 4)
        self.api_handlers["CreateFileW"] = self._create_file
        self.api_handlers["ReadFile"] = self._read_file
        self.api_handlers["CloseHandle"] = lambda p: (1, 4)
        # The training file (section 5) in memory by name, so what is kept across a load is real.
        self.disk: dict[str, bytes] = {}
        self.last_error = 0
        for name, fn in (("CreateFileA", self._create_file_a), ("WriteFile", self._write_file),
                         ("FlushFileBuffers", lambda p: (1, 4)), ("MoveFileExA", self._move_file),
                         ("DeleteFileA", self._delete_file), ("GetLastError", lambda p: (p.last_error, 0)),
                         ("CreateDirectoryA", lambda p: (1, 8)), ("SHGetSpecialFolderPathA", self._documents)):
            self.api_handlers[name] = fn
        self.clock = 1000
        self.api_handlers["GetTickCount"] = lambda p: (p.clock, 0)
        self.tick = 5000
        self.stub(RAND, self._rand)
        self.stub(GAME, lambda p: (GAME_OBJECT, 0))
        self.mu.mem_map(GAME_OBJECT, 0x20000)
        self.put32(GAME_OBJECT + DIFFICULTY, 1)
        self.put32(GAME_OBJECT + NONI, 500)
        self.put32(GAME_OBJECT + CROPS, 300)
        self.put32(FOOD, 4000)
        self.put32(PEOPLE_CURED, 7)
        self.texts = self.alloc(0x100)
        self.words = self.alloc(0x4000)
        self.stub(TEXTS, lambda p: (self.texts, 0))
        self.stub(TEXT, self._text)
        self.stub(STOP, self._stop)
        self.stub(START, self._start)
        self.stub(POSITION, self._position)
        self.stub(HEATHEN_AI, self._stock_ai)
        self.teacher = 0                                    # 0x43A810: someone teaching at the nursery school
        self.stub(TEACHER, lambda p: (self.teacher, 0))
        self.put32(MEDICINE, 1)
        for puzzle in range(32):                            # every puzzle unsolved unless a test solves it
            self.put32(PUZZLE_NEEDED + 4 * puzzle, 1)
            self.put32(PUZZLE_PROGRESS + 8 * puzzle, 0)
        self.write(MAP, LCMAP.read_bytes())                 # the real walk map (0x4775B0 loads it here)
        for area in range(0x87):                            # its 135 area boxes "to be measured" (0x4775B4)
            self.write(MAP + 0x64010 + 0x14 * area, b"\x01")
        manager, slots = self._table(bytes(exe))
        self.records, self.slots = manager + 0x48, slots
        self.export("VvfpStartup", 5, 0)
        self.installed = self.export("VvfpHeathenLifeInstalled")

    @staticmethod
    def _file_offset(exe: bytes, va: int) -> int:
        import pefile
        pe = pefile.PE(data=exe, fast_load=True)
        return pe.get_offset_from_rva(va - pe.OPTIONAL_HEADER.ImageBase)

    @staticmethod
    def _table(exe: bytes) -> tuple[int, int]:
        import pefile
        pe = pefile.PE(data=exe, fast_load=True)
        base = pe.OPTIONAL_HEADER.ImageBase
        manager = struct.unpack("<I", pe.get_data(0x94051, 4))[0]
        slots = struct.unpack("<I", pe.get_data(0x1F1E6, 4))[0]
        if manager == BIG_MANAGER and slots == BIG_SLOTS:
            return BIG_MANAGER, BIG_SLOTS
        return base + 0x154148, STOCK_SLOTS

    # ---- stand-ins --------------------------------------------------------------------------------------
    def _create_file(self, p):
        name = p.wstring(p.arg(0))
        if self.options is not None and name.endswith(OPTIONS):
            handle = 0x700 + 4 * len(self.files)
            self.files[handle] = [self.options.encode(), 0]
            return handle, 28
        return 0xFFFFFFFF, 28

    def _read_file(self, p):
        data, pos = self.files[p.arg(0)][:2]
        chunk = data[pos:pos + p.arg(2)]
        p.write(p.arg(1), chunk)
        p.put32(p.arg(3), len(chunk))
        self.files[p.arg(0)][1] = pos + len(chunk)
        return 1, 20

    def _documents(self, p):
        p.write(p.arg(1), b"C:\\Docs\0")
        return 1, 16

    def _create_file_a(self, p):
        name, disposition = p.cstring(p.arg(0)), p.arg(4)
        if disposition == 3 and name not in self.disk:               # OPEN_EXISTING
            self.last_error = 2
            return 0xFFFFFFFF, 28
        if disposition != 3:
            self.disk[name] = b""
        handle = 0x900 + 4 * len(self.files)
        self.files[handle] = [self.disk[name], 0, name]
        return handle, 28

    def _write_file(self, p):
        entry = self.files[p.arg(0)]
        entry[0] += p.read(p.arg(1), p.arg(2))
        self.disk[entry[2]] = entry[0]
        p.put32(p.arg(3), p.arg(2))
        return 1, 20

    def _move_file(self, p):
        self.disk[p.cstring(p.arg(1))] = self.disk.pop(p.cstring(p.arg(0)))
        return 1, 12

    def _delete_file(self, p):
        return int(self.disk.pop(p.cstring(p.arg(0)), None) is not None), 4

    def save_slot(self, slot: int) -> None:
        """The game's save manager (0x4DACE0) with its slot field (+0x17D80), as a loaded village has it."""
        if not getattr(self, "save_manager", 0):
            self.save_manager = self.alloc(0x17D80 + 0x10)
            self.put32(0x4DACE0, self.save_manager)
        self.put32(self.save_manager + 0x17D80, slot)

    def _rand(self, p):
        self.rand_calls += 1
        return 0, 0

    def _text(self, p):
        at = self.words + 0x20 * (p.arg(0) & 0x1FF)
        p.write(at, f"T{p.arg(0):X}".encode() + b"\0")
        return at, 4

    def _stop(self, p):
        record = p.reg("ecx")
        self.stopped.append(record)
        p.write(record, bytes(STEP * STEPS))
        p.put32(record + BEHAVIOUR, 0)
        return 0, 0

    def _start(self, p):
        self.started.append(p.reg("ecx"))
        return 0, 0

    def _position(self, p):
        out = p.arg(0)
        x, y = self.positions.get(p.reg("ecx"), (1990, 1610))
        p.put32(out, x)
        p.put32(out + 4, y)
        return out, 4

    def _stock_ai(self, p):
        self.stock_ai.append(p.reg("ecx"))
        return 0, 0

    # ---- records ----------------------------------------------------------------------------------------
    def record(self, index: int) -> int:
        return self.records + index * STRIDE

    def villager(self, index: int, *, heathen: bool = True, age: int = 600, role: int = 0, sex: int = 0,
                 health: int = 90, skills: tuple[float, ...] = (0.0,) * 6, likes: tuple[int, ...] = (1, 2, 3),
                 dislikes: tuple[int, ...] = (4, 5, 6)) -> int:
        r = self.record(index)
        self.write(r, bytes(STRIDE))
        self.write(r + NAME, f"V{index}".encode() + b"\0")
        self.put32(r + AGE, age)
        self.put32(r + SEX, sex)
        self.put32(r + HEALTH, health)
        self.put32(r + CAUSE, 0xFFFFFFFF)
        self.write(r + SKILLS, struct.pack("<6f", *skills))
        self.write(r + LIKES, struct.pack("<3I", *likes))
        self.write(r + DISLIKES, struct.pack("<3I", *dislikes))
        self.write(r + PRESENT, b"\x01")
        self.write(r + FACTION, b"\x01" if heathen else b"\x00")
        self.put32(r + ROLE, role)
        return r

    def i32(self, record: int, offset: int) -> int:
        return struct.unpack("<i", self.read(record + offset, 4))[0]

    def skill(self, record: int, which: int) -> float:
        return struct.unpack("<f", self.read(record + SKILLS + 4 * which, 4))[0]

    def sick(self, record: int) -> bool:
        return self.read(record + SICK, 1) != b"\0"

    def steps(self, record: int) -> list[tuple[int, ...]]:
        out = []
        for k in range(STEPS):
            words = struct.unpack("<22I", self.read(record + k * STEP, STEP))
            if words[0] == 0:
                break
            out.append(words)
        return out

    def solve(self, puzzle: int) -> None:
        self.put32(PUZZLE_PROGRESS + 8 * puzzle, 1)

    def build(self, site: int, project: int, area: int, cells: int = 6) -> None:
        """A building put up: its object's project (+8) and walk area (+0x14), and its area stamped on the map."""
        obj = SITE_OBJECTS[site]
        self.put32(obj + 8, project)
        self.put32(obj + 0x14, area)
        self.solve(project)
        self.stamp(area, site, cells)

    def stamp(self, area: int, row: int, cells: int = 6) -> None:
        """A walk area stamped into a few cells of its own (x 1000.., y 1200 + 64 x row; the area bits only), as
        the game stamps a built building's area into the map."""
        for k in range(cells):
            cell = (1200 // 8 + 8 * row) * 320 + 1000 // 8 + k
            word = self.u32(MAP + 4 * cell)
            self.put32(MAP + 4 * cell, (word & ~(0x7FF << 4)) | (area << 4))
        self.tick += 3000                                   # the companion looks at the map afresh

    def drag_cure(self, healer: int, patient: int) -> None:
        """The drag-a-healer cure 0x468C10 (thiscall on the healer), the game's code from its start to its end;
        stood in for: its patient finder 0x4706F0 (answers `patient`), the skill check 0x46B270 (a pass), the
        messages 0x413450, the behaviour starter 0x465580, the say step 0x474910 and the step pop 0x4733F0."""
        self.stub(0x4706F0, lambda p: (patient, 0xC))
        self.stub(0x46B270, lambda p: (1, 8))
        self.stub(0x413450, lambda p: (0, 8))
        self.stub(0x465580, lambda p: (0, 8))
        self.stub(0x474910, lambda p: (0, 4))
        self.stub(0x4733F0, lambda p: (0, 4))
        self.call(0x468C10, ecx=healer)

    # ---- the game ---------------------------------------------------------------------------------------
    def unit(self, record: int, flags: int = HE_LIFE_UNIT | HE_LIFE_ROW) -> int:
        return self.export("VvfpHeathenLifeUnit", record, flags)

    def pick(self, record: int) -> None:
        """The picker 0x46F070 from its faction test 0x46F0BA: esi = edx = the record, ebx = 0, its frame (saved
        esi and ebx, 8 bytes of locals) on the stack above the return."""
        esp = STACK_TOP - 0x2000
        self.put32(esp + PICK_FRAME, RETURN)
        self.set_reg("esp", esp)
        self.set_reg("esi", record)
        self.set_reg("edx", record)
        self.set_reg("ebx", 0)
        self.run(PICK_SITE, RETURN)

    def snapshot(self, skip: list[tuple[int, int]]) -> bytes:
        """The believers' state: the executable's data from .data on (the villager table, food, statistics,
        projects, techs) and the village object, with `skip` ranges (the acting Heathens' records, the walk
        map's own area-box cache) blanked."""
        start = 0x4C0000
        end = self.exe_base + self.exe_size
        data = bytearray(self.read(start, end - start))
        for begin, length in skip + [(MAP + 0x64000, 2048 * 20)]:
            lo, hi = max(begin, start), min(begin + length, end)
            if lo < hi:
                data[lo - start:hi - start] = bytes(hi - lo)
        return bytes(data) + self.read(GAME_OBJECT, 0x20000)


def _skip() -> str | None:
    if not HAVE_EMULATOR:
        return "unicorn/pefile not installed"
    if not stock_path(5).is_file():
        return "stock executable not present (inputs/)"
    if not LCMAP.is_file():
        return "research/game-data/vv5/lcmap.dat not present"
    if not DLL.is_file():
        return f"{DLL} missing"
    return None


# Each look's Details text as it starts (where the Heathen is going; the patcher's own labels, English with no
# translation chosen), and the texts its text steps (type 6, 0x474270) change it to, in order.
TEXT_NONI, TEXT_CROPS, TEXT_FISH = "Going to the noni bushes", "Going to the farm plots", "Going fishing at the lake"
TEXT_POOLS, TEXT_STATUE, TEXT_LAB = "Going to the pools", "Going to the statue", "Going to the lab"
TEXT_LOVE, TEXT_CLOTHING = "Going to the love shack", "Going to the clothing hut"
TEXT_NURSERY = "T35"                                        # the game's own "Going to play in the nursery"
TEXT_SICK, TEXT_EATING, TEXT_PRAISING = "Going home to the camp, sick", "Going to eat at the camp", "Going to the mud hut"
TEXT_WAITING = "Waiting for the healer"
BACK = "Going back to the camp"
THEN = {
    TEXT_NONI: ["Practising Farming at the noni bushes", "Bringing noni home to the camp",
                "Dropping off noni at the camp"],
    TEXT_CROPS: ["Practising Farming at the farm plots", "Bringing crops home to the camp",
                 "Dropping off crops at the camp"],
    TEXT_FISH: ["Practising Farming at the lake", "Bringing a fish home to the camp",
                "Dropping off a fish at the camp"],
    TEXT_POOLS: ["Relaxing by the pools", BACK],
    TEXT_STATUE: ["Practising Devotion at the statue", BACK],
    TEXT_LAB: ["Practising Research at the lab", BACK],
    TEXT_LOVE: ["Waiting at the love shack", BACK],
    TEXT_CLOTHING: ["Looking at the clothes", BACK],
    TEXT_NURSERY: ["Playing in the nursery", BACK],
    TEXT_SICK: ["Resting at the camp, sick"],
    TEXT_EATING: ["Eating at the camp"],
    TEXT_PRAISING: ["Practising Devotion at the mud hut", BACK],
}
LEISURE_THEN = {
    "Going to the stream": ["Cooling their feet in the stream", BACK],
    "Going to wash in the stream": ["Washing in the stream", BACK],
    "Going off to relax": ["Relaxing for a while", BACK],
    "Going to watch the clouds": ["Watching the clouds go by", BACK],
    "Going to the lake": ["Relaxing by the lake", BACK],
    "Going to the waterfall": ["Admiring the waterfall", BACK],
    "Going off to dance": ["Dancing for fun", BACK],
    "Going to bathe": ["Having a bath", BACK],
}
THEN.update(LEISURE_THEN)
CAMP_TEXTS = {TEXT_EATING, TEXT_PRAISING}
FINDS = {
    "Picking up a mushroom": ("Bringing a mushroom to camp", "Dropping off a mushroom", {0x80}),
    "Picking up a rare mushroom": ("Bringing a rare mushroom to camp", "Dropping off a rare mushroom", {0x81}),
    "Picking up a golden mushroom": ("Bringing a golden mushroom to camp", "Dropping off a golden mushroom",
                                     {0x82}),
    "Picking up lab equipment": ("Bringing lab equipment to camp", "Dropping off lab equipment",
                                 set(range(0x50, 0x68))),
    "Picking up a relic": ("Bringing a relic to camp", "Dropping off a relic", set(range(0x68, 0x80))),
}
FIND_GOING = {"Going to look for mushrooms", "Going to look for collectibles"}
# Section 5's pace, out of the way of the tests of the looks: every Heathen may go out after one unit.
FREE = "show_percent=100\nouting_cooldown=1\naway_max=64\nsame_action_max=64\n"
DOORS = {TEXT_LOVE, TEXT_CLOTHING}
HARVESTS = {TEXT_NONI: (2, NONI_AREA, 0), TEXT_CROPS: (5, CROP_AREA, 0), TEXT_FISH: (10, LAKE, 0x38)}
TEXT_STEP = 6
LONGEST_STOCK_DETAILS = 37          # "Talking "mommy to mommy" with heathen" (0x268), the game's longest


def said(steps: list) -> list[str]:
    """The texts of a queue's text steps (type 6: the text at the step's +0x28), in order."""
    out = []
    for s in steps:
        if s[0] == TEXT_STEP:
            raw = struct.pack("<22I", *s)[0x28:0x28 + 0x27]
            out.append(raw.split(b"\0", 1)[0].decode("cp1252"))
    return out


def _inside(box: tuple[int, int, int, int], x: int, y: int) -> bool:
    return box[0] <= x <= box[2] + 7 and box[1] <= y <= box[3] + 7


class _Base(unittest.TestCase):
    areas: ClassVar[dict[int, tuple[int, int, int, int]]] = {}

    @classmethod
    def setUpClass(cls) -> None:
        if not cls.areas:
            _Base.areas = _areas()

    def picks(self, camp: Camp, record: int, count: int, want: str | None = None,
              advance: bool = True) -> list[tuple[str, list]]:
        """Up to `count` picks of a record with an empty queue: (Details text, steps) of each look queued.  With
        `advance`, one life unit of the record before each (section 5's cool-down counts units; a sickness it
        brings is taken away again)."""
        out = []
        for _ in range(count):
            if advance:
                camp.unit(record)
                camp.write(record + SICK, b"\x00")
            camp.write(record, bytes(STEP * STEPS))
            camp.write(record + DOING, bytes(0x27))
            camp.pick(record)
            out.append((camp.cstring(record + DOING), camp.steps(record)))
            if want is not None and out[-1][0] == want:
                break
        return out

    def walks(self, steps: list) -> list[tuple[int, int, int]]:
        return [(s[1], s[2], s[3]) for s in steps if s[0] == 4]      # (distance, x, y)


@unittest.skipIf(_skip(), _skip() or "")
class Installs(_Base):
    def test_the_row_installs_the_picker_splice_and_nothing_without_it(self):
        camp = Camp()
        self.assertEqual(camp.installed, 1)
        self.assertEqual(camp.read(PICK_SITE, 1), b"\xE9")
        off = Camp(row=False)
        self.assertEqual(off.installed, 0)
        self.assertEqual(off.read(PICK_SITE, 8), bytes.fromhex("389AEC1C0000740D"))
        sick = off.villager(3)
        off.write(sick + SICK, b"\x01")
        self.assertEqual(off.unit(sick), 0)                 # the stock rule: the skip clears the byte

    def test_another_patchs_bytes_at_the_picker_install_nothing(self):
        camp = Camp(spoil_site=True)
        self.assertEqual(camp.installed, 0)
        self.assertNotEqual(camp.read(PICK_SITE, 1), b"\xE9")
        sick = camp.villager(3)
        camp.write(sick + SICK, b"\x01")
        self.assertEqual(camp.unit(sick), 0)
        self.assertEqual(camp.unit(sick, HE_LIFE_IDLE | HE_LIFE_ROW), 0)

    def test_every_population_mode(self):
        """The three population modes (stock, collection_progression, immediate_fixed), each with and without 256
        Villagers (Experimental): the splice installs on each render, the bridge finds the last record of that
        build's own table (the 256 build's manager 0x800000), and a pick queues a look."""
        big = with_requirements(5, ["vv5_population_256"])
        for mode in ("stock", "collection_progression", "immediate_fixed"):
            for rows, slots in (((), STOCK_SLOTS), (big, BIG_SLOTS)):
                with self.subTest(mode=mode, slots=slots):
                    self._one_mode(render(5, rows, mode), slots)

    def _one_mode(self, exe: bytes, slots: int) -> None:
        camp = Camp(exe=exe, options="show_percent=100\n")
        self.assertEqual(camp.installed, 1)
        self.assertEqual(camp.slots, slots)
        last = camp.villager(camp.slots - 1)
        self.assertEqual(camp.unit(last, HE_LIFE_IDLE | HE_LIFE_ROW), HANDLED)
        camp.write(last + SICK, b"\x01")
        self.assertEqual(camp.unit(last, HE_LIFE_IDLE | HE_LIFE_ROW), KEEP_SICK | HANDLED)
        camp.write(last + SICK, b"\x00")
        camp.pick(last)
        self.assertEqual(camp.started, [last])
        self.assertEqual(camp.stock_ai, [])


@unittest.skipIf(_skip(), _skip() or "")
class BridgeBits(_Base):
    def test_the_return_bits(self):
        camp = Camp()
        heathen = camp.villager(3)
        believer = camp.villager(4, heathen=False)
        dead = camp.villager(5, health=0)
        row_idle, row_unit = HE_LIFE_IDLE | HE_LIFE_ROW, HE_LIFE_UNIT | HE_LIFE_ROW
        self.assertEqual(camp.unit(heathen, HE_LIFE_UNIT), 0, "without HE_LIFE_ROW: the stock rule")
        self.assertEqual(camp.unit(heathen, HE_LIFE_IDLE), 0)
        self.assertEqual(camp.unit(believer, row_idle), 0)
        self.assertEqual(camp.unit(dead, row_idle), 0)
        self.assertEqual(camp.unit(camp.record(3) + 4, row_idle), 0, "not a record's start")
        self.assertEqual(camp.unit(0x12345678, row_idle), 0, "outside the table")
        self.assertEqual(camp.unit(heathen, row_idle), HANDLED)
        camp.write(heathen + SICK, b"\x01")
        self.assertEqual(camp.unit(heathen, row_idle), KEEP_SICK | HANDLED)
        self.assertEqual(camp.unit(heathen, row_unit), KEEP_SICK | HANDLED)
        self.assertTrue(camp.sick(heathen), "no doctor and one unit: still sick (1 in 240 to get well alone)")


@unittest.skipIf(_skip(), _skip() or "")
class Sickness(_Base):
    def test_a_heathen_falls_sick_by_the_believers_rule_and_looks_it(self):
        camp = Camp()
        r = camp.villager(3, age=1200)                      # an elder at Medicine 1: 1,000 + 160 = 1,160
        for _ in range(1500):
            camp.unit(r)
            if camp.sick(r):
                break
        self.assertTrue(camp.sick(r))
        self.assertIn(r, camp.stopped)                      # as 0x472FAC stops a believer
        self.assertEqual(camp.cstring(r + DOING), TEXT_SICK)
        walks = self.walks(camp.steps(r))
        self.assertEqual(walks[0][0], 0x28)                 # the sick pace
        self.assertTrue(_inside(self.areas[CAMP], walks[0][1], walks[0][2]), "at the encampment")
        self.assertIn(9, [s[1] for s in camp.steps(r) if s[0] == 3], "the believers' sick pose (animation 9)")
        self.assertEqual(camp.u32(r + BEHAVIOUR), 0x9C)

    def test_the_easiest_difficulty_halves_the_rolls_twice(self):
        counts = {}
        for difficulty in (0, 1):
            camp = Camp()
            camp.put32(GAME_OBJECT + DIFFICULTY, difficulty)
            r = camp.villager(3, age=400)                   # not an elder: Medicine 1, rand(1440) <= 3
            n = 0
            for _ in range(6000):
                camp.unit(r)
                if camp.sick(r):
                    n += 1
                    camp.write(r + SICK, b"\x00")
            counts[difficulty] = n
        # 6,000 units: about 16.7 at difficulty 1, a quarter of that at 0.
        self.assertGreater(counts[1], 8)
        self.assertLess(counts[0], counts[1])
        self.assertLess(counts[0], 10)

    def test_the_puzzle_heathens_never_fall_sick(self):
        camp = Camp()
        for role in range(12, 18):
            r = camp.villager(3, age=1200, role=role)
            for _ in range(1500):
                camp.unit(r)
            self.assertFalse(camp.sick(r), role)

    def test_a_sick_heathen_never_drops_below_the_floor_and_gets_well_alone(self):
        for options, floor in ((None, 21), ("sick_floor=40\n", 40)):
            with self.subTest(floor=floor):
                camp = Camp(options=options)
                r = camp.villager(3, health=floor + 9)
                camp.write(r + SICK, b"\x01")
                lowest, units = 100, 0
                while camp.sick(r) and units < 5000:
                    camp.unit(r)
                    units += 1
                    lowest = min(lowest, camp.i32(r, HEALTH))
                self.assertFalse(camp.sick(r), "no Heathen can heal: well on their own")
                self.assertEqual(lowest, floor, "down to the floor, never below")
                self.assertEqual(camp.u32(r + CAUSE), 0xFFFFFFFF)

    def test_a_quiet_unit_never_draws_the_games_rand(self):
        camp = Camp()
        r = camp.villager(3, role=13, health=50)            # the Chief: never sick, no look queued
        for _ in range(500):
            camp.unit(r)
        self.assertEqual(camp.rand_calls, 0)
        self.assertEqual(camp.i32(r, HEALTH), 100, "a well Heathen heals by the believers' +1")

    def test_nothing_reads_a_heathens_sex(self):
        text = SOURCE.read_text(encoding="utf-8")
        self.assertNotIn("0x1B90", text)
        self.assertNotIn("R_SEX", text)


@unittest.skipIf(_skip(), _skip() or "")
class Doctors(_Base):
    def _camp(self, healing: float = 100.0):
        camp = Camp()
        patient = camp.villager(5)
        camp.write(patient + SICK, b"\x01")
        camp.positions[patient] = (1950, 1600)
        doctor = camp.villager(6, role=4, skills=(0, 0, healing, 0, 0, 0), likes=(LEARNING, 2, 3))
        puzzle = camp.villager(7, role=12, skills=(0, 0, 100, 0, 0, 0), likes=(LEARNING, 2, 3))
        believer = camp.villager(8, heathen=False, skills=(0, 0, 100, 0, 0, 0))
        return camp, patient, doctor, puzzle, believer

    def test_a_heathen_doctor_heals_and_people_cured_never_moves(self):
        camp, patient, doctor, puzzle, believer = self._camp()
        untouched = (camp.read(puzzle, STRIDE), camp.read(believer, STRIDE))
        camp.unit(patient)
        self.assertEqual(camp.cstring(doctor + DOING), "Going to heal V5")
        self.assertEqual(said(camp.steps(doctor)), ["Practising Healing on V5", BACK])
        self.assertEqual(camp.cstring(patient + DOING), TEXT_WAITING)
        first = self.walks(camp.steps(doctor))[0]
        self.assertEqual(first, (0x96, 1950, 1610), "the believers' healer walk: the patient's spot +10 down")
        self.assertTrue(camp.sick(patient))
        camp.unit(patient)
        self.assertFalse(camp.sick(patient))
        self.assertEqual(camp.u32(PEOPLE_CURED), 7, "Heathen cures never count in People Cured")
        self.assertEqual(camp.skill(doctor, HEALING), 100.0)
        self.assertEqual((camp.read(puzzle, STRIDE), camp.read(believer, STRIDE)), untouched)

    def test_the_doctor_practises_healing(self):
        camp, patient, doctor, _, _ = self._camp(healing=50.0)
        camp.unit(patient)
        camp.unit(patient)
        self.assertFalse(camp.sick(patient))
        self.assertEqual(camp.skill(doctor, HEALING), 52.0, "(70 - 50) / 18 = 1, doubled for liking Learning")

    def test_the_puzzle_heathen_doctor_is_never_one_of_them(self):
        camp = Camp()
        patient = camp.villager(5)
        camp.write(patient + SICK, b"\x01")
        puzzle = camp.villager(7, role=12, skills=(0, 0, 100, 0, 0, 0), likes=(LEARNING, 2, 3))
        before = camp.read(puzzle, STRIDE)
        units = 0
        while camp.sick(patient) and units < 5000:
            camp.unit(patient)
            units += 1
        self.assertFalse(camp.sick(patient), "with no Heathen able to heal, well on their own")
        self.assertGreater(units, 1)
        self.assertNotIn(puzzle, camp.stopped)
        self.assertEqual(camp.read(puzzle, STRIDE), before)
        self.assertEqual(camp.u32(PEOPLE_CURED), 7)


@unittest.skipIf(_skip(), _skip() or "")
class ShowHarvests(_Base):
    def test_each_harvest_waits_for_its_puzzle(self):
        camp = Camp(options=FREE)
        r = camp.villager(3)
        seen = {text for text, _ in self.picks(camp, r, 120)}
        self.assertFalse(seen & set(HARVESTS), "no puzzle solved: no harvest")
        opened: set[str] = set()
        for text, (puzzle, _, _) in HARVESTS.items():
            camp.solve(puzzle)
            opened.add(text)
            seen = {t for t, _ in self.picks(camp, r, 600, want=text)}
            self.assertIn(text, seen, f"puzzle {puzzle} solved")
            self.assertFalse((seen & set(HARVESTS)) - opened, "only the opened sources")

    def test_a_harvest_takes_nothing_and_walks_to_the_encampment(self):
        camp = Camp(options=FREE)
        r = camp.villager(3)
        for puzzle, _, _ in HARVESTS.values():
            camp.solve(puzzle)
        for text, (_, area, item) in HARVESTS.items():
            with self.subTest(harvest=text):
                found = None
                for _ in range(800):
                    camp.unit(r)
                    camp.write(r + SICK, b"\x00")
                    before = camp.snapshot([(r, STRIDE)])
                    (got, steps), = self.picks(camp, r, 1, advance=False)
                    self.assertEqual(camp.snapshot([(r, STRIDE)]), before, got)
                    if got == text:
                        found = steps
                        break
                self.assertIsNotNone(found)
                types = [s[0] for s in found]
                self.assertNotIn(SKILL_CHECK_STEP, types)
                self.assertNotIn(PAYOFF_STEP, types)
                walks = self.walks(found)
                self.assertTrue(_inside(self.areas[area], walks[0][1], walks[0][2]), "to the source")
                carried = types.index(0x12)
                self.assertEqual(found[carried][1], item)
                after = [s for s in found[carried:] if s[0] == 4]
                self.assertTrue(after and _inside(self.areas[CAMP], after[0][2], after[0][3]),
                                "carried to the encampment")
                self.assertFalse(_inside(self.areas[5], after[0][2], after[0][3]), "never the granary")
                self.assertEqual(types[-1], 0x13, "dropped there")
        self.assertEqual(camp.u32(GAME_OBJECT + NONI), 500)
        self.assertEqual(camp.u32(GAME_OBJECT + CROPS), 300)
        self.assertEqual(camp.u32(FOOD), 4000)


@unittest.skipIf(_skip(), _skip() or "")
class Facilities(_Base):
    def test_each_facility_visit_leaves_the_believers_state_byte_identical(self):
        camp = Camp(options=FREE)
        r = camp.villager(3)
        believer = camp.villager(4, heathen=False, skills=(50,) * 6)   # a believer whose record must not move
        camp.positions[believer] = (6000, 6000)            # away from every place (section 5: believers first)
        camp.solve(14)                                      # the Believer Idol carved
        camp.build(5, 24, 0x20)                             # the Nursery Hut: never an adult's visit
        camp.build(4, 23, 0x11)                             # the Love Shack
        camp.build(3, 22, 0x10)                             # the Clothing Hut
        camp.teacher = 1
        stamped = {0x11: 4, 0x10: 3}
        want = {TEXT_POOLS: POOLS, TEXT_STATUE: STATUE, TEXT_LAB: LAB}
        waiting_sites: set[int] = set()
        for _ in range(1500):
            camp.unit(r)
            camp.write(r + SICK, b"\x00")
            before = camp.snapshot([(r, STRIDE)])
            (text, steps), = self.picks(camp, r, 1, advance=False)
            self.assertEqual(camp.snapshot([(r, STRIDE)]), before, text)
            types = {s[0] for s in steps}
            self.assertNotIn(SKILL_CHECK_STEP, types)
            self.assertNotIn(PAYOFF_STEP, types)
            walks = self.walks(steps)
            if text in want:
                area = want.pop(text)
                if area in stamped:
                    self.assertEqual(walks[0][2] // 8 - 1200 // 8, 8 * stamped[area], text)
                else:
                    self.assertTrue(_inside(self.areas[area], walks[0][1], walks[0][2]), text)
                self.assertTrue(_inside(self.areas[CAMP], walks[-1][1], walks[-1][2]), "back to the encampment")
            elif text in DOORS:                             # the Love Shack's or the Clothing Hut's door
                self.assertLessEqual(types, {3, 4, 0x0B, TEXT_STEP}, "no embrace, no clothes")
                row = (walks[0][2] // 8 - 1200 // 8) // 8
                self.assertEqual(row, 4 if text == TEXT_LOVE else 3, text)
                waiting_sites.add(row)
            self.assertNotEqual(text, TEXT_NURSERY, "adults never go to the nursery")
            if not want and waiting_sites == {3, 4}:
                break
        self.assertEqual(want, {})
        self.assertEqual(waiting_sites, {3, 4})

    def test_unbuilt_buildings_and_an_uncarved_idol_are_never_visited(self):
        camp = Camp(options=FREE)
        r = camp.villager(3)
        seen = {text for text, _ in self.picks(camp, r, 300)}
        self.assertFalse(seen & ({TEXT_STATUE, TEXT_NURSERY} | DOORS))
        self.assertTrue({TEXT_POOLS, TEXT_LAB, TEXT_EATING, TEXT_PRAISING} <= seen)

    def test_children_puzzle_heathens_and_believers_keep_the_stock_ai(self):
        camp = Camp(options=FREE)
        # (a child with nobody teaching at the nursery school: the stock children's routine)
        for record in (camp.villager(3, age=100), camp.villager(4, role=13), camp.villager(5, role=17)):
            camp.pick(record)
            self.assertEqual(camp.steps(record), [])
        self.assertEqual(len(camp.stock_ai), 3)
        camp.put32(WEATHER, 3)                              # rain: the stock shelter
        r = camp.villager(6)
        camp.pick(r)
        self.assertEqual(len(camp.stock_ai), 4)


@unittest.skipIf(_skip(), _skip() or "")
class AgeBands(_Base):
    """The owner (2026-11-26): Heathens do only what believers of their age do.  Children (under 280 units): only
    the nursery play, while someone teaches at the nursery school (0x46E433..0x46E472); adults and elders: every
    adult action (no age test in the dispatcher, chooser or player's job); the Love Shack door: 360 to 999 (the
    partner search 0x470A53 / 0x470A8F)."""

    def _camp(self) -> Camp:
        camp = Camp(options=FREE)
        for puzzle in (2, 5, 10, 14):
            camp.solve(puzzle)
        camp.build(4, 23, 0x11)                             # the Love Shack, its cells in row 4
        camp.build(3, 22, 0x10)                             # the Clothing Hut, row 3
        camp.stamp(0x22, 6)                                 # the nursery's play area, row 6
        return camp

    def _seen(self, camp: Camp, record: int, count: int) -> tuple[set[str], set[int]]:
        texts, door_rows = set(), set()
        for text, steps in self.picks(camp, record, count):
            texts.add(text)
            walks = self.walks(steps)
            if text in DOORS:
                door_rows.add((walks[0][2] // 8 - 1200 // 8) // 8)
        return texts, door_rows

    def test_a_child_plays_in_the_nursery_only_while_someone_teaches_and_brings_finds_home(self):
        camp = self._camp()
        child = camp.villager(3, age=200)
        texts, _ = self._seen(camp, child, 40)
        self.assertLessEqual(texts, {""} | FIND_GOING, "nobody teaching: finds or the stock children's routine")
        self.assertTrue(texts & FIND_GOING)
        camp.teacher = 1
        seen = set()
        for text, steps in self.picks(camp, child, 60):
            self.assertIn(text, {TEXT_NURSERY, ""} | FIND_GOING)
            seen.add(text)
            if text == TEXT_NURSERY:
                walks = self.walks(steps)
                self.assertEqual(walks[0][2] // 8 - 1200 // 8, 8 * 6, "to the nursery's play area 0x22")
                self.assertTrue(_inside(self.areas[CAMP], walks[-1][1], walks[-1][2]))
        self.assertIn(TEXT_NURSERY, seen)
        self.assertEqual(camp.u32(child + SKILLS + 4 * PARENTING), 0)

    def test_adults_never_go_to_the_nursery_and_do_adult_work(self):
        camp = self._camp()
        camp.teacher = 1
        r = camp.villager(3, age=280)
        texts, _ = self._seen(camp, r, 700)
        self.assertNotIn(TEXT_NURSERY, texts)
        self.assertFalse(texts & FIND_GOING, "a find is a child's")
        self.assertTrue({TEXT_NONI, TEXT_CROPS, TEXT_FISH, TEXT_POOLS, TEXT_STATUE, TEXT_LAB, TEXT_EATING,
                         TEXT_PRAISING} <= texts, texts)

    def test_elders_retired_to_the_encampment_do_only_what_is_done_there(self):
        """The owner (2026-11-26): elders "retire and go to the encampment" -- from the game's elder age (1,000 at
        Medicine 1, 0x46F790) a show action is a meal or devotion at the mud hut, never a walk away."""
        camp = self._camp()
        camp.teacher = 1
        for age in (1000, 2000):
            with self.subTest(age=age):
                r = camp.villager(3, age=age)
                texts, rows = self._seen(camp, r, 150)
                shown = texts - {""}
                self.assertTrue(shown and shown <= {TEXT_EATING, TEXT_PRAISING}, texts)
                self.assertEqual(rows, set(), "no building door")

    def test_the_love_shack_door_only_at_the_couples_ages(self):
        camp = self._camp()
        for age, love in ((280, False), (359, False), (360, True), (999, True)):
            with self.subTest(age=age):
                r = camp.villager(3, age=age)
                _, rows = self._seen(camp, r, 900)
                self.assertIn(3, rows, "the Clothing Hut door is any adult's below the elder age")
                self.assertEqual(4 in rows, love)


@unittest.skipIf(_skip(), _skip() or "")
class PeopleCured(_Base):
    """The drag-a-healer cure 0x468C10 counts People Cured (0x468D4D); a patient who is a Heathen when the cure
    begins never counts, with or without the Village Statistics row (whose own guard is left in place)."""

    def _cure(self, camp: Camp, heathen: bool) -> int:
        # (not disliking preference 4, which 0x468C83 tests before its own extra roll)
        healer = camp.villager(8, heathen=False, skills=(0, 0, 80, 0, 0, 0), dislikes=(7, 8, 9))
        patient = camp.villager(9, heathen=heathen)
        camp.write(patient + SICK, b"\x01")
        before = camp.u32(PEOPLE_CURED)
        camp.drag_cure(healer, patient)
        self.assertFalse(camp.sick(patient), "the game's own cure still cures")
        return camp.u32(PEOPLE_CURED) - before

    def test_a_heathen_patient_never_counts_and_a_believer_does(self):
        camp = Camp()
        self.assertEqual(camp.read(CURE_BEGIN, 1), b"\xE9")
        self.assertEqual(camp.read(CURE_COUNT, 1), b"\xE9")
        self.assertEqual(self._cure(camp, heathen=True), 0)
        self.assertEqual(self._cure(camp, heathen=False), 1)

    def test_without_the_row_nothing_changes_the_stock_count(self):
        camp = Camp(row=False)
        self.assertEqual(self._cure(camp, heathen=True), 1, "the stock game (no row) counts it")

    def test_the_statistics_rows_guard_is_left_alone(self):
        rows = with_requirements(5, ["vv5_write_village_statistics"])
        exe = render(5, rows, "collection_progression")
        camp = Camp(exe=exe)
        self.assertEqual(camp.installed, 1)
        begin, count = camp.read(CURE_BEGIN, 8), camp.read(CURE_COUNT, 7)
        stock = Camp(exe=exe, row=False)
        self.assertEqual((begin, count), (stock.read(CURE_BEGIN, 8), stock.read(CURE_COUNT, 7)),
                         "the row's detours, never patched twice")
        self.assertEqual(self._cure(camp, heathen=True), 0)
        self.assertEqual(self._cure(camp, heathen=False), 1)

    def test_other_bytes_at_a_cure_site_install_nothing(self):
        exe = bytearray(stock_path(5).read_bytes())
        exe[Camp._file_offset(bytes(exe), CURE_COUNT + 6)] = 0x02
        camp = Camp(exe=bytes(exe))
        self.assertEqual(camp.installed, 0)
        self.assertEqual(camp.read(PICK_SITE, 8), bytes.fromhex("389AEC1C0000740D"), "all or none")


@unittest.skipIf(_skip(), _skip() or "")
class Skills(_Base):
    def _after_show(self, text: str, which: int, value: float) -> float:
        camp = Camp(options=FREE)
        skills = [0.0] * 6
        skills[which] = value
        r = camp.villager(3, role=1, skills=tuple(skills), likes=(LEARNING, 2, 3))
        self.assertEqual(self.picks(camp, r, 800, want=text)[-1][0], text)
        camp.unit(r)
        return camp.skill(r, which)

    def test_a_show_actions_skill_grows_by_the_believers_rule(self):
        # 34 + 66 (liking Learning) passes every roll; (70 - 34) / 18 = 2, doubled: 4.
        self.assertEqual(self._after_show(TEXT_LAB, RESEARCH, 34.0), 38.0)
        self.assertEqual(self._after_show(TEXT_PRAISING, DEVOTION, 34.0), 38.0, "Devotion at the mud hut")

    def test_role_practice_from_nothing(self):
        camp = Camp()
        camp.put32(MEDICINE, 3)                             # sickness rare (rand(5400) <= 2): practice not paused
        r = camp.villager(3, role=4, dislikes=(LEARNING, 5, 6))   # Healing, from 0, disliking Learning
        for _ in range(400):
            camp.unit(r)
            if camp.skill(r, HEALING) != 0.0:
                break
        # A pass: 7 from 0, halved: 3.  A failure at exactly 0: 4 (0x469D90).
        self.assertIn(camp.skill(r, HEALING), (3.0, 4.0))

    def test_a_skill_at_100_stays_and_others_are_untouched(self):
        camp = Camp()
        r = camp.villager(3, role=4, skills=(10, 20, 100, 30, 40, 50))
        for _ in range(400):
            camp.unit(r)
        self.assertEqual([camp.skill(r, k) for k in range(6)], [10.0, 20.0, 100.0, 30.0, 40.0, 50.0])


@unittest.skipIf(_skip(), _skip() or "")
class Labels(_Base):
    """The owner (2026-11-27): "please change them to describe where they are going and what they are doing", then
    "and practicing skills too".  Each look starts with where the Heathen is going; the game's own text step (type
    6, 0x474270) changes it, right after the walk, to what they do there ("Practising <skill> at <place>" where a
    skill is practised), and again on the way back."""

    def _camp(self) -> Camp:
        camp = Camp(options=FREE)
        for puzzle in (2, 5, 10, 14):
            camp.solve(puzzle)
        camp.build(4, 23, 0x11)
        camp.build(3, 22, 0x10)
        camp.stamp(0x22, 6)
        camp.teacher = 1
        return camp

    def _check(self, text: str, steps: list) -> None:
        self.assertIn(text, THEN, text)
        self.assertEqual(said(steps), THEN[text], text)
        types = [s[0] for s in steps]
        first_walk = types.index(4)
        self.assertEqual(types[first_walk + 1], TEXT_STEP, f"{text}: the 'there' text right after the walk")
        last = len(types) - 1 - types[::-1].index(TEXT_STEP)
        if THEN[text][-1] == BACK:
            self.assertEqual(types[last + 1], 4, f"{text}: the way-back text right before the walk back")
        if text in HARVESTS:
            self.assertEqual(types[last - 1], 4, f"{text}: dropping off right after the walk to the encampment")
            self.assertEqual(types[last - 2], TEXT_STEP, f"{text}: bringing it home right before that walk")
            self.assertEqual(types[-1], 0x13, f"{text}: the drop step last")

    def test_every_adult_look_says_where_and_what(self):
        camp = self._camp()
        r = camp.villager(3, age=600)
        wanted = set(THEN) - {TEXT_NURSERY, TEXT_SICK}
        for text, steps in self.picks(camp, r, 2000):
            if text == "":
                continue                                      # a chat with nobody free: the stock AI
            self._check(text, steps)
            wanted.discard(text)
            if not wanted:
                break
        self.assertEqual(wanted, set())

    def test_the_childs_nursery_play_and_the_sick_look(self):
        camp = self._camp()
        child = camp.villager(3, age=200)
        text, steps = self.picks(camp, child, 200, want=TEXT_NURSERY)[-1]
        self.assertEqual(text, TEXT_NURSERY)
        self._check(text, steps)
        sick = camp.villager(4)
        camp.write(sick + SICK, b"\x01")
        (text, steps), = self.picks(camp, sick, 1, advance=False)
        self.assertEqual(text, TEXT_SICK)
        self._check(text, steps)

    def test_a_long_patient_name_keeps_the_doctors_lines_whole(self):
        for name, going in ((b"Kalahuna Moonwhisperers", "Going to heal Kalahuna Moonwhisperers"),
                            (b"Kalahuna Moonwhisperer X", "Going to heal someone sick")):   # 23, 24 characters
            with self.subTest(name=name):
                camp = Camp()
                patient = camp.villager(5)
                camp.write(patient + NAME, name + b"\0")
                camp.write(patient + SICK, b"\x01")
                doctor = camp.villager(6, role=4, skills=(0, 0, 50, 0, 0, 0))
                camp.unit(patient)
                self.assertEqual(camp.cstring(doctor + DOING), going)
                self.assertEqual(said(camp.steps(doctor)), ["Practising Healing on the sick", BACK],
                                 "too long with the name: the line without it, never cut")

    def test_every_label_fits_like_the_games_own(self):
        import re
        text = SOURCE.read_text(encoding="utf-8")
        labels = re.findall(r'vvfp_trf?\("vvfp\.heathen_life/[^"]+", "([^"]+)"', text)
        self.assertEqual(len(labels), 83)
        for english in labels:
            shown = english.replace("%s", "")
            self.assertLessEqual(len(shown), LONGEST_STOCK_DETAILS, english)
            self.assertNotIn("Waiting for someone", english)
        self.assertIn("#define LABEL_LONGEST 37", text)
        self.assertIn("R_DOING_CAP", text)


AWAY_FIRST = ({TEXT_NONI, TEXT_CROPS, TEXT_FISH, TEXT_POOLS, TEXT_STATUE, TEXT_LAB} | DOORS | set(LEISURE_THEN)
              | FIND_GOING)
ENCOUNTER, NEAR_TEST, ORANGE_TEST, BEHAVIOUR_START = 0x46E2E0, 0x476260, 0x4661F0, 0x452BD0
ORANGE, RED, FAITH, CARRY, SELF = 0x1CED, 0x1CEE, 0x1CF0, 0x1D0C, 0x1B88


@unittest.skipIf(_skip(), _skip() or "")
class Pace(_Base):
    """The owner (2026-11-28): "heathens shouldn't all en-masse do a single action or stay in the encampment all the
    time. just occasional walking and doing stuff per heathen"; the believers stay primary; Quiet / Normal / Lively."""

    def _tribe(self, options: str, size: int) -> tuple[Camp, list[int]]:
        camp = Camp(options=options)
        for puzzle in (2, 5, 10, 14):
            camp.solve(puzzle)
        records = [camp.villager(i, age=400 + i) for i in range(size)]
        for r in records:
            for _ in range(40):                            # every one past its cool-down
                camp.unit(r)
            camp.write(r + SICK, b"\x00")
        return camp, records

    def test_a_tribe_of_fifty_never_goes_out_en_masse(self):
        for busy, away_cap, same_cap in (("1", 3, 1), ("2", 6, 2), ("3", 8, 3)):
            with self.subTest(busyness=busy):
                camp, records = self._tribe(f"show_percent=100\nbusyness={busy}\n", 50)
                texts = [self.picks(camp, r, 1, advance=False)[0][0] for r in records]
                out = [t for t in texts if t in AWAY_FIRST]
                self.assertLessEqual(len(out), away_cap, out)
                self.assertGreater(len(out), 0)
                for text in set(texts) - {""}:
                    self.assertLessEqual(texts.count(text), same_cap, text)
                self.assertGreater(texts.count(""), 30, "most of the camp goes on with the game's own life")

    def test_each_heathen_waits_its_cool_down_between_outings(self):
        camp = Camp(options="show_percent=100\nouting_cooldown=5\n")
        r = camp.villager(3)
        for _ in range(6):
            camp.unit(r)
        outings, units = [], 0
        for k in range(120):
            if k % 3 == 0:
                camp.unit(r)
                camp.write(r + SICK, b"\x00")
                units += 1
            (text, _), = self.picks(camp, r, 1, advance=False)
            if text in AWAY_FIRST:
                outings.append(units)
        self.assertGreater(len(outings), 3)
        gaps = [b - a for a, b in itertools.pairwise(outings)]
        self.assertTrue(all(gap >= 5 for gap in gaps), gaps)   # 5 units between outings
        self.assertIn(5, gaps, "and out again once the cool-down has passed")

    def test_nobody_stays_at_the_encampment_for_ever(self):
        camp = Camp(options="show_percent=1\nouting_cooldown=2\n")
        r = camp.villager(3)
        for _ in range(9):                                # 4 cool-downs and more
            camp.unit(r)
        (text, _), = self.picks(camp, r, 1, advance=False)
        self.assertNotEqual(text, "", "overdue: the next idle moment is a show action, whatever show_percent says")

    def test_a_place_a_believer_stands_in_is_left_to_the_believers(self):
        camp = Camp(options=FREE)
        r = camp.villager(3)
        box = self.areas[LAB]
        believer = camp.villager(4, heathen=False)
        camp.positions[believer] = (box[0] + 8, box[1] + 8)
        texts = {t for t, _ in self.picks(camp, r, 400)}
        self.assertNotIn(TEXT_LAB, texts)
        camp.positions[believer] = (6000, 6000)
        camp.tick += 3000
        texts = {t for t, _ in self.picks(camp, r, 400, want=TEXT_LAB)}
        self.assertIn(TEXT_LAB, texts)


@unittest.skipIf(_skip(), _skip() or "")
class Chats(_Base):
    def test_a_heathen_chats_with_an_idle_believer_and_nothing_of_theirs_changes(self):
        camp = Camp(options=FREE)
        r = camp.villager(3)
        b = camp.villager(4, heathen=False)
        camp.put32(b + BEHAVIOUR, 0x13)                   # relaxing
        camp.put32(b + CARRY, 0xFFFFFFFF)
        camp.put32(b + FAITH, 55)
        camp.positions[b] = (6000, 6000)
        for text, steps in self.picks(camp, r, 600):
            if text == "Going to chat with V4":
                break
        else:
            self.fail("no chat with the idle believer")
        self.assertEqual(said(steps)[0], "Chatting with V4")
        self.assertEqual(camp.cstring(b + DOING), "Chatting with V3")
        self.assertIn(b, camp.stopped)
        self.assertEqual([s[1] for s in camp.steps(b) if s[0] == 3], [0x10], "the listening pose (animation 0x10)")
        self.assertEqual(camp.u32(b + FAITH), 55, "no Faith change")
        self.assertEqual(self.walks(steps)[0][1:], (6000 + 0x14, 6000 + 0x4B), "up to the believer")

    def test_a_believer_at_work_carrying_or_held_is_never_asked(self):
        camp = Camp(options=FREE)
        r = camp.villager(3)
        busy = [camp.villager(4 + k, heathen=False) for k in range(3)]
        camp.put32(busy[0] + BEHAVIOUR, 0x6C)              # harvesting noni
        camp.put32(busy[0] + CARRY, 0xFFFFFFFF)
        camp.put32(busy[1] + BEHAVIOUR, 0x13)
        camp.put32(busy[1] + CARRY, 0x38)                  # carrying a fish
        camp.put32(busy[2] + BEHAVIOUR, 0x13)
        camp.put32(busy[2] + CARRY, 0xFFFFFFFF)
        camp.write(busy[2] + HELD, b"\x01")                # the player holds them
        for b in busy:
            camp.positions[b] = (6000, 6000)
        self.picks(camp, r, 400)
        for b in busy:
            self.assertNotIn(b, camp.stopped)

    def test_two_heathens_chat_at_the_encampment(self):
        camp = Camp(options=FREE)
        r = camp.villager(3)
        other = camp.villager(4)
        camp.put32(other + BEHAVIOUR, 0x9C)                # the camp wander
        for text, steps in self.picks(camp, r, 600):
            if text == "Going to chat with V4":
                break
        else:
            self.fail("no chat")
        self.assertEqual(camp.cstring(other + DOING), "Chatting with V3")


@unittest.skipIf(_skip(), _skip() or "")
class Masks(_Base):
    """The owner (2026-11-27): "orange ones can still chase believers. red ones can still repel believers too."  The
    chase and the fright are the game's own encounter 0x46E2E0, started by nearness, whatever the Heathen is doing."""

    def _encounter(self, camp: Camp, heathen_record: int, believer: int) -> int:
        started: list[tuple[int, int]] = []
        camp.stub(NEAR_TEST, lambda p: (0, 0))
        camp.stub(ORANGE_TEST, lambda p: (0, 0))
        camp.stub(BEHAVIOUR_START, lambda p: (started.append((p.arg(0), p.arg(1))) or 0, 0xC))
        for r in (heathen_record, believer):
            camp.put32(r + SELF, r)
        esp = STACK_TOP - 0x3000
        camp.put32(esp, RETURN)
        camp.put32(esp + 4, believer)
        camp.set_reg("esp", esp)
        camp.set_reg("ecx", heathen_record)
        camp.run(ENCOUNTER, RETURN)
        return camp.reg("eax") & 0xFF

    def test_a_show_action_never_stops_a_chase_or_a_fright(self):
        for mask, heathen_behaviour, believer_behaviour in ((ORANGE, 0x14, 0x15), (RED, None, 0x16)):
            with self.subTest(mask=hex(mask)):
                camp = Camp(options=FREE)
                h = camp.villager(3)
                camp.write(h + mask, b"\x01")
                b = camp.villager(4, heathen=False)
                (text, _), = [x for x in self.picks(camp, h, 50) if x[0]][:1] or [("", [])]
                self.assertNotEqual(text, "", "the Heathen is on a show action")
                self.assertEqual(camp.u32(h + BEHAVIOUR), 0x9C)
                self.assertEqual(self._encounter(camp, h, b), 1, "the game's own encounter still starts")
                self.assertEqual(camp.u32(b + BEHAVIOUR), believer_behaviour)
                if heathen_behaviour is not None:
                    self.assertEqual(camp.u32(h + BEHAVIOUR), heathen_behaviour)

    def test_a_chasing_heathen_is_never_stopped_for_sickness_a_doctor_or_a_chat(self):
        camp = Camp(options=FREE)
        chaser = camp.villager(5, skills=(0, 0, 100, 0, 0, 0))
        camp.put32(chaser + BEHAVIOUR, 0x14)
        patient = camp.villager(6)
        camp.write(patient + SICK, b"\x01")
        camp.unit(patient)
        self.assertNotIn(chaser, camp.stopped, "never the doctor while chasing")
        talker = camp.villager(7)
        self.picks(camp, talker, 300)
        self.assertNotIn(chaser, camp.stopped, "never a chat partner while chasing")
        camp.put32(MEDICINE, 1)
        camp.write(chaser + SICK, b"\x00")
        for _ in range(3000):
            camp.unit(chaser)
            if camp.sick(chaser):
                break
        self.assertTrue(camp.sick(chaser))
        self.assertNotIn(chaser, camp.stopped, "sick, but the chase goes on")
        self.assertEqual(camp.u32(chaser + BEHAVIOUR), 0x14)


@unittest.skipIf(_skip(), _skip() or "")
class Finds(_Base):
    def test_a_childs_find_is_only_a_picture(self):
        camp = Camp(options=FREE)
        child = camp.villager(3, age=200)
        seen = set()
        for _ in range(400):
            camp.unit(child)
            camp.write(child + SICK, b"\x00")
            before = camp.snapshot([(child, STRIDE)])
            (text, steps), = self.picks(camp, child, 1, advance=False)
            self.assertEqual(camp.snapshot([(child, STRIDE)]), before, "nothing of the believers' changes")
            if text not in FIND_GOING:
                continue
            first, carry_text, drop_text = said(steps)
            self.assertIn(first, FINDS)
            carry_label, drop_label, items = FINDS[first]
            self.assertEqual((carry_text, drop_text), (carry_label, drop_label))
            carried = [s[1] for s in steps if s[0] == 0x12]
            self.assertEqual(len(carried), 1)
            self.assertIn(carried[0], items)
            types = [s[0] for s in steps]
            self.assertEqual(types[-1], 0x13, "set down")
            walks = self.walks(steps)
            self.assertTrue(_inside(self.areas[CAMP], walks[-1][1], walks[-1][2]), "at the encampment")
            self.assertFalse(any(_inside(self.areas[a], walks[-1][1], walks[-1][2]) for a in (5, 0x0D, 0x36)),
                             "never where the drop handler counts it")
            self.assertNotIn(SKILL_CHECK_STEP, types)
            self.assertNotIn(PAYOFF_STEP, types)
            seen.add(first)
            # Cut short: the picture is taken away by a plain write, never a drop.
            camp.put32(child + CARRY, carried[0])
            self.picks(camp, child, 1)
            self.assertEqual(camp.i32(child, CARRY), -1)
            if seen == set(FINDS):
                break
        self.assertEqual(seen, set(FINDS))


@unittest.skipIf(_skip(), _skip() or "")
class Training(_Base):
    """The owner (2026-11-27): "the untrained heathens should be allowed to choose a skill and practice it and
    eventually master them (same rate as believers, always evenly-distributed)"."""

    def test_untrained_heathens_choose_evenly_and_the_choice_is_kept_across_a_load(self):
        camp = Camp(options=FREE)
        camp.save_slot(2)
        records = [camp.villager(i, age=400 + i, role=0) for i in range(12)]
        for r in records:
            camp.clock += 2000
            camp.unit(r)
        camp.clock += 2000
        camp.unit(records[0])
        files = [name for name in camp.disk if name.endswith("Heathen Training - Save 2.dat")]
        self.assertEqual(len(files), 1, list(camp.disk))
        data = camp.disk[files[0]]
        magic, version, game, count, slot = struct.unpack_from("<5I", data)
        self.assertEqual((magic, version, game, count, slot), (0x31534856, 1, 5, 12, 2))
        skills = [struct.unpack_from("<2I", data, 20 + 8 * k)[1] for k in range(count)]
        self.assertEqual(sorted(skills.count(k) for k in range(6)), [2] * 6, "always evenly-distributed")
        # A new session: the same choices come back from the file.
        again = Camp(options=FREE)
        again.disk = dict(camp.disk)
        again.save_slot(2)
        for i in range(12):
            again.villager(i, age=400 + i, role=0)
        again.unit(again.record(0))
        again.clock += 2000
        again.write(again.record(5) + SKILLS, struct.pack("<6f", 25, 0, 0, 0, 0, 0))   # no longer untrained
        again.unit(again.record(5))
        again.clock += 2000
        again.unit(again.record(0))
        kept = again.disk[files[0]]
        self.assertEqual(kept[20:], data[20:], "kept by identity, never chosen again")

    def test_a_trainee_practises_its_skill_and_moves_on_once_mastered(self):
        camp = Camp(options=FREE)
        camp.save_slot(1)
        r = camp.villager(3, role=0, likes=(LEARNING, 2, 3))
        camp.unit(r)
        camp.clock += 2000
        camp.unit(r)
        name = next(n for n in camp.disk if n.endswith("Save 1.dat"))
        chosen = struct.unpack_from("<2I", camp.disk[name], 20)[1]
        start = camp.skill(r, chosen)
        self.picks(camp, r, 200)
        self.assertGreater(camp.skill(r, chosen), start, "practised by the believers' check")
        camp.write(r + SKILLS + 4 * chosen, struct.pack("<f", 100.0))
        camp.clock += 2000
        camp.unit(r)
        camp.clock += 2000
        camp.unit(r)
        after = struct.unpack_from("<2I", camp.disk[name], 20)[1]
        self.assertNotEqual(after, chosen, "mastered: the next skill")


@unittest.skipIf(_skip(), _skip() or "")
class UnfinishedStatue(_Base):
    """The owner (2026-11-27): "same skill practice rules apply to heathens with the heathen expansion patch too" --
    as a believer dropped on the statue carved to stage 1 or 2 (PR #898), a Heathen's visit there is half the time
    Devotion practised and half the time the believers' Confused look."""

    def test_stage_one_or_two_honors_or_is_confused_half_and_half(self):
        for stage in (1, 2):
            with self.subTest(stage=stage):
                camp = Camp(options=FREE)
                camp.put32(0x51D950 + 8, stage)            # carved, the Idol puzzle not solved
                r = camp.villager(3, role=1, skills=(0, 0, 0, 0, 0, 34.0), likes=(LEARNING, 2, 3))
                kinds = {"Practising Devotion at the statue": 0, "Confused at the unfinished statue": 0}
                for text, steps in self.picks(camp, r, 1500):
                    if text == TEXT_STATUE:
                        kinds[said(steps)[0]] += 1
                        types = [s[0] for s in steps]
                        self.assertNotIn(SKILL_CHECK_STEP, types)
                        self.assertNotIn(PAYOFF_STEP, types)
                self.assertGreater(kinds["Practising Devotion at the statue"], 3, kinds)
                self.assertGreater(kinds["Confused at the unfinished statue"], 3, kinds)

    def test_a_confused_visit_practises_nothing(self):
        camp = Camp(options=FREE)
        camp.put32(0x51D950 + 8, 1)
        r = camp.villager(3, role=1, skills=(0, 0, 0, 0, 0, 34.0), likes=(LEARNING, 2, 3))
        for text, steps in self.picks(camp, r, 2000):
            if text == TEXT_STATUE and said(steps)[0] == "Confused at the unfinished statue":
                break
        else:
            self.fail("no Confused visit")
        before = camp.skill(r, DEVOTION)
        camp.unit(r)
        self.assertEqual(camp.skill(r, DEVOTION), before, "Confused: no Devotion practised")

    def test_stage_zero_or_three_is_as_before(self):
        camp = Camp(options=FREE)
        r = camp.villager(3)
        for stage in (0, 3):
            camp.put32(0x51D950 + 8, stage)
            self.assertNotIn(TEXT_STATUE, {t for t, _ in self.picks(camp, r, 300)}, "not carved / not unfinished")


if __name__ == "__main__":
    unittest.main()
