"""New Believers: Heathens who age, die of old age, are replaced, and (the tribe row) have children -- the four rows
of "VVFP Heathen Aging.dll" (the owner, 2026-11-22):

* "Former Villagers Keep Aging Among the Heathens" (flag "VVFP Heathen Aging Former.txt"): only our villagers who
  became Heathens age, and can die of old age by the believers' own rule;
* "Heathen Tribe Ages, Dies and Has Children" (flag "VVFP Heathen Aging Tribe.txt"): every Heathen, the puzzle
  Heathens too ("PUZZLE HEATHENS TOO (IF THEY DIE ANOTHER ONE IMMEDIATELY SPAWNS IN"), and Heathen babies;
* "Former Villagers Among the Heathens Leave Skeletons" / "All Heathens Leave Skeletons" (flags "VVFP Heathen
  Skeletons Former.txt" / "... All.txt"): who leaves a body the believers bury; without them a Heathen who dies
  disappears, logged, no grave.

EMULATED on the stock New Believers executable: the companion is started as the start-up chain starts it; then the
game's own age credit (its faction test 0x470077 to the record's end 0x4700E8), its own life tick 0x472C90 (whole,
every pass) and its own to-a-Heathen 0x4669E0 run on hand-made records.  The game routines the Heathen path calls are
stood in for: rand 0x403660 (answers queued by the test), SetHealth 0x4758B0 (writes health and cause, and bumps the
Village Statistics' death counter 0x51D3A0 as its hook does), the Heathen creator 0x46FD20 (the first free record),
the conception routine 0x465E00, the carry 0x466420, the activity stop 0x473440, and the Cause of Death companion's
two exports.
"""
from __future__ import annotations

import collections
import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

try:
    from test_companion_installs_all_or_none import HAVE_EMULATOR, Machine, stock_path
    from story_emulator import STACK_TOP
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

DLL = ROOT / "assets" / "heathen_aging" / "VVFP Heathen Aging.dll"
FORMER, TRIBE = "VVFP Heathen Aging Former.txt", "VVFP Heathen Aging Tribe.txt"
BONES_FORMER, BONES_ALL = "VVFP Heathen Skeletons Former.txt", "VVFP Heathen Skeletons All.txt"

MANAGER = 0x554148
RECORDS = MANAGER + 0x48
STRIDE = 0x2F44
AGE, SEX, LINEAGE, NAME, HEAD, BODY = 0x1B8C, 0x1B90, 0x1B98, 0x1B9C, 0x1BB8, 0x1BBC
FATHER_NAME, MOTHER_NAME, FATHER_HEAD, FATHER_BODY, MOTHER_HEAD, MOTHER_BODY = (
    0x1BC0, 0x1BD9, 0x1BF4, 0x1BF8, 0x1BFC, 0x1C00)
BABY_FATHER_NAME, BABY_FATHER_BODY, BABY_FATHER_HEAD = 0x1C10, 0x1C2C, 0x1C30
STAMP, PROCESSED, HEALTH, CAUSE, SICK, PREGNANT, LITTER, SKILLS = (
    0x1C38, 0x1C3C, 0x1C40, 0x1C44, 0x1C48, 0x1C4C, 0x1C50, 0x1C5C)
PRESENT, FACTION, ORANGE, RED, FAITH, ROLE = 0x1CD4, 0x1CEC, 0x1CED, 0x1CEE, 0x1CF0, 0x1CFC
LIKES = 0x1F5C
DEATHS_STAT, OLDEST_STAT, MEDICINE = 0x51D3A0, 0x51D378, 0x51D5D0
TWINS, TRIPLETS = 0x51D380, 0x51D384
PUZZLE_PROGRESS, PUZZLE_NEEDED = 0x51E008, 0x51DF30
CREDIT_SITE, CREDIT_END, LIFE_TICK, TO_HEATHEN = 0x470077, 0x4700E8, 0x472C90, 0x4669E0
GAME_OBJECT = 0x30000000
COD = 0x0B200000
PARENTAGE = 0x0B300000          # "VVFP Parentage Export.dll", as GetModuleHandleA hands it back here
# Medicine 1: old age from 1,100 units (55 years): a roll at each whole year past it.
OLD = 1100


class Village(Machine):
    # The villager table (the 256 build's in tests/test_vv5_heathen_evolution.py).
    manager, slots = MANAGER, 150

    def __init__(self, flags: tuple[str, ...], *, statistics_form: bool = False, cod: bool = True):
        exe = bytearray(stock_path(5).read_bytes())
        self.edit_exe(exe)
        super().__init__(bytes(exe), DLL, present=flags)
        if statistics_form:
            # The Village Statistics rows' Oldest Villager guard (`jne` 0C -> 38 at 0x47007F), in this emulated
            # image only: the companion must follow the branch it finds there.
            self.write(0x470080, b"\x38")
        self.rand_answers: collections.deque[int] = collections.deque()
        self.rand_calls: list[int] = []
        self.created: list[tuple[int, list[int]]] = []
        self.conceived: list[tuple[int, list[int]]] = []
        self.stopped: list[int] = []
        self.died: list[tuple[int, int, int]] = []
        self.arrived: list[tuple[int, str]] = []
        self.cod = cod
        self.api_handlers["GetModuleHandleA"] = self._module
        self.api_handlers["GetProcAddress"] = self._proc
        # A clock that moves, so the companion's file and grave watch run at each age credit (every 250 ms live).
        self.clock = 0
        self.api_handlers["GetTickCount"] = self._clock
        # Files in memory (the companion's per-save file), so what it keeps across a Change Tribe is real.
        self.files: dict[str, bytes] = {}
        self.handles: dict[int, list] = {}
        self.last_error = 0
        for name, fn in (("CreateFileA", self._create_file), ("ReadFile", self._read_file),
                         ("WriteFile", self._write_file), ("FlushFileBuffers", lambda p: (1, 4)),
                         ("CloseHandle", self._close), ("MoveFileExA", self._move_file),
                         ("DeleteFileA", self._delete_file), ("GetLastError", lambda p: (p.last_error, 0)),
                         ("CreateDirectoryA", lambda p: (1, 8)), ("SHGetSpecialFolderPathA", self._documents)):
            self.api_handlers[name] = fn
        stubs = self.alloc(0x40)
        self.cod_exports = {"VvfpCauseDiedAmongHeathens": stubs, "VvfpCauseHeathenArrived": stubs + 0x10,
                            "VvfpCauseNoteArrival": stubs + 0x20}
        self.parentage_exports = {"WriteParentageBirthLitter": stubs + 0x30}
        self.noted: list[int] = []
        self.births: list[tuple[str, list[int]]] = []
        self.stub(stubs, self._cod_died)
        self.stub(stubs + 0x10, self._cod_arrived)
        self.stub(stubs + 0x20, self._cod_noted)
        self.stub(stubs + 0x30, self._birth)
        self.stub(0x403660, self._rand)
        self.stub(0x4758B0, self._set_health)
        self.stub(0x46FD20, self._create)
        self.stub(0x465E00, self._conceive)
        self.stub(0x466420, lambda p: (0, 4))
        self.stub(0x473440, self._stop)
        self.stub(0x4653D0, lambda p: (0, 0))
        self.stub(0x470800, lambda p: (0, 0))
        self.stub(0x44EF60, lambda p: (0, 8))          # to-a-Heathen's bottom-bar message
        self.stub(0x466880, self._faction)
        self.stub(0x425950, lambda p: (GAME_OBJECT, 0))  # the age credit's game object (speed)
        self.mu.mem_map(GAME_OBJECT, 0x20000)
        self.put32(GAME_OBJECT + 0x17D7C, 6)
        self.put32(MEDICINE, 1)
        for puzzle in range(32):                         # every puzzle unsolved unless a test solves it
            self.put32(PUZZLE_NEEDED + 4 * puzzle, 1)
        self.before_start()
        self.installed = self.export("VvfpStartup", 5, 0)
        self.installed = self.export("VvfpHeathenAgingInstalled")

    def edit_exe(self, exe: bytearray) -> None:
        """The executable as this test runs it (a subclass may change it before it is mapped)."""

    def before_start(self) -> None:
        """Anything a subclass sets up before the companion starts."""

    def _documents(self, p):
        p.write(p.arg(1), b"C:\\Docs\0")
        return 1, 16

    def _create_file(self, p):
        name, disposition = p.cstring(p.arg(0)), p.arg(4)
        if disposition == 3 and name not in self.files:              # OPEN_EXISTING
            self.last_error = 2
            return 0xFFFFFFFF, 28
        if disposition != 3:
            self.files[name] = b""
        handle = 0x500 + len(self.handles) * 4
        self.handles[handle] = [name, 0]
        return handle, 28

    def _read_file(self, p):
        name, pos = self.handles[p.arg(0)]
        data = self.files[name][pos:pos + p.arg(2)]
        p.write(p.arg(1), data)
        p.put32(p.arg(3), len(data))
        self.handles[p.arg(0)][1] = pos + len(data)
        return 1, 20

    def _write_file(self, p):
        name = self.handles[p.arg(0)][0]
        self.files[name] += p.read(p.arg(1), p.arg(2))
        p.put32(p.arg(3), p.arg(2))
        return 1, 20

    def _close(self, p):
        self.handles.pop(p.arg(0), None)
        return 1, 4

    def _move_file(self, p):
        src, dst = p.cstring(p.arg(0)), p.cstring(p.arg(1))
        self.files[dst] = self.files.pop(src)
        return 1, 12

    def _delete_file(self, p):
        return int(self.files.pop(p.cstring(p.arg(0)), None) is not None), 4

    def _clock(self, p):
        self.clock += 1000
        return self.clock, 0

    # ---- stand-ins ----------------------------------------------------------------------------------------
    def _module(self, p):
        name = p.arg(0)
        if name == 0:
            return 0x400000, 4
        if self.cod and p.cstring(name) == "VVFP Parentage Export.dll":
            return PARENTAGE, 4
        return (COD if self.cod and p.cstring(name) == "VVFP Cause of Death.dll" else 0), 4

    def _proc(self, p):
        if p.arg(0) == COD:
            return self.cod_exports.get(p.cstring(p.arg(1)), 0), 8
        if p.arg(0) == PARENTAGE:
            return self.parentage_exports.get(p.cstring(p.arg(1)), 0), 8
        return 0, 8

    def _cod_noted(self, p):
        self.noted.append(p.arg(1))
        return 0, 8

    def _birth(self, p):
        args = [p.arg(i) for i in range(12)]
        self.births.append((p.cstring(args[1]), args))
        return 1, 48

    def _cod_died(self, p):
        self.died.append((p.arg(0), p.arg(1), p.arg(2)))
        return 0, 12

    def _cod_arrived(self, p):
        self.arrived.append((p.arg(1), p.cstring(p.arg(2))))
        return 0, 12

    def _rand(self, p):
        n = p.arg(0)
        self.rand_calls.append(n)
        value = self.rand_answers.popleft() if self.rand_answers else n - 1
        return value % n, 0

    def _set_health(self, p):
        block = p.reg("ecx")
        value, cause = p.arg(0), p.arg(1)
        if struct.unpack("<i", p.read(block + 0xC, 4))[0] > 0 and value <= 0:
            p.put32(DEATHS_STAT, p.u32(DEATHS_STAT) + 1)
        p.put32(block + 0xC, value)
        p.put32(block + 0x10, cause if value <= 0 else 0xFFFFFFFF)
        return 0, 8

    def _faction(self, p):
        p.write(p.reg("ecx") + FACTION, bytes([p.arg(0) & 0xFF]))
        return 0, 4

    def _stop(self, p):
        self.stopped.append(p.reg("ecx"))
        return 0, 0

    def _create(self, p):
        args = [struct.unpack("<i", p.read(p.reg("esp") + 4 + 4 * i, 4))[0] for i in range(9)]
        for index in range(self.slots):
            if p.read(self.record(index) + PRESENT, 1) == b"\0":
                break
        else:
            return 0xFFFFFFFF, 0x24
        lineage, skill, value, sex, age, orange, red, role, faith = args
        r = self.record(index)
        self.write(r, bytes(STRIDE))
        self.write(r + NAME, f"New{index}".encode() + b"\0")
        self.write(r + LIKES, struct.pack("<3I", index, 7, 9))
        self.put32(r + LINEAGE, lineage)
        self.put32(r + SEX, 1 if sex == -1 else sex)
        self.put32(r + AGE, age)
        self.put32(r + PROCESSED, age)
        self.put32(r + HEALTH, 90)
        self.put32(r + CAUSE, 0xFFFFFFFF)
        self.put32(r + HEAD, 11)
        self.put32(r + FAITH, faith)
        self.write(r + PRESENT, b"\x01")
        self.write(r + FACTION, b"\x01")
        self.write(r + ORANGE, bytes([orange]))
        self.write(r + RED, bytes([red]))
        self.put32(r + ROLE, role)
        self.created.append((index, args))
        return index, 0x24

    def _conceive(self, p):
        carrier = p.reg("ecx")
        args = [p.u32(p.reg("esp") + 4 + 4 * i) for i in range(7)]
        self.conceived.append((carrier, args))
        p.put32(carrier + PREGNANT, p.u32(carrier + PROCESSED))
        p.put32(carrier + LITTER, 1)
        name = p.cstring(args[3])[:24].encode()
        p.write(carrier + BABY_FATHER_NAME, name + b"\0")
        p.put32(carrier + BABY_FATHER_HEAD, args[4])
        p.put32(carrier + BABY_FATHER_BODY, args[5])
        p.put32(TWINS, p.u32(TWINS) + 1)               # as the routine counts its roll
        return 0, 0x1C

    # ---- records ------------------------------------------------------------------------------------------
    def record(self, index: int) -> int:
        return self.manager + 0x48 + index * STRIDE

    def villager(self, index: int, *, heathen: bool, age: int = 600, role: int = 0, sex: int = 0,
                 parents: bool = False, orange: int = 0, red: int = 0, name: str | None = None) -> int:
        r = self.record(index)
        self.write(r, bytes(STRIDE))
        self.write(r + NAME, (name or f"V{index}").encode() + b"\0")
        self.write(r + LIKES, struct.pack("<3I", 1, index, 3))
        self.put32(r + AGE, age)
        self.put32(r + PROCESSED, age)
        self.put32(r + SEX, sex)
        self.put32(r + HEALTH, 90)
        self.put32(r + CAUSE, 0xFFFFFFFF)
        self.put32(r + STAMP, 1)
        self.put32(r + HEAD, 5)
        self.write(r + PRESENT, b"\x01")
        self.write(r + FACTION, b"\x01" if heathen else b"\x00")
        self.write(r + ORANGE, bytes([orange]))
        self.write(r + RED, bytes([red]))
        self.put32(r + ROLE, role)
        self.put32(r + FAITH, (-50 if heathen else 40) & 0xFFFFFFFF)
        if parents:
            self.write(r + FATHER_NAME, b"Dad\0")
            self.write(r + MOTHER_NAME, b"Mum\0")
        return r

    def i32(self, record: int, offset: int) -> int:
        return struct.unpack("<i", self.read(record + offset, 4))[0]

    # ---- the game -----------------------------------------------------------------------------------------
    def credit(self, record: int, units: int) -> None:
        """The age credit from its faction test to the record's end: esi the record, eax the units, ebx 0."""
        self.set_reg("esp", STACK_TOP - 0x2000)
        self.set_reg("esi", record)
        self.set_reg("eax", units)
        self.set_reg("ebx", 0)
        self.run(CREDIT_SITE, CREDIT_END)

    def life_tick(self) -> None:
        self.call(LIFE_TICK, ecx=self.manager)

    def turn_heathen(self, record: int) -> None:
        self.call(TO_HEATHEN, ecx=record)

    def solve(self, puzzle: int) -> None:
        self.put32(PUZZLE_NEEDED + 4 * puzzle, 1)
        self.put32(PUZZLE_PROGRESS + 8 * puzzle, 1)

    def unsolve(self, puzzle: int) -> None:
        self.put32(PUZZLE_NEEDED + 4 * puzzle, 1)
        self.put32(PUZZLE_PROGRESS + 8 * puzzle, 0)


def _skip() -> str | None:
    if not HAVE_EMULATOR:
        return "unicorn/pefile not installed"
    if not stock_path(5).is_file():
        return "stock executable not present (inputs/)"
    if not DLL.is_file():
        return f"{DLL} missing"
    return None


def _due_to_die(v: Village, record: int, *, at: int = OLD + 20) -> None:
    """Age `at` (a whole year past old age) with that one unit still to process, and the roll answering 0."""
    v.put32(record + AGE, at + 1)
    v.put32(record + PROCESSED, at)
    v.rand_answers.extend([0])


@unittest.skipIf(_skip(), _skip() or "")
class Installs(unittest.TestCase):
    def test_nothing_without_an_aging_row(self):
        for flags in ((), (BONES_ALL,), (BONES_FORMER,)):
            with self.subTest(flags=flags):
                v = Village(flags)
                self.assertEqual(v.installed, 0)
                h = v.villager(1, heathen=True)
                v.credit(h, 5)
                self.assertEqual(v.i32(h, AGE), 600, "the stock game: a Heathen never ages")

    def test_installs_with_either_aging_row_and_either_credit_form(self):
        for flags in ((FORMER,), (TRIBE,), (FORMER, TRIBE, BONES_ALL)):
            for form in (False, True):
                with self.subTest(flags=flags, statistics_form=form):
                    self.assertEqual(Village(flags, statistics_form=form).installed, 1)


@unittest.skipIf(_skip(), _skip() or "")
class FormerVillagers(unittest.TestCase):
    def _converted(self, v: Village, index: int = 3, **kw) -> int:
        r = v.villager(index, heathen=False, **kw)
        v.credit(r, 1)                                   # seen alive as a believer
        self.assertEqual(v.i32(r, AGE), 601)
        v.turn_heathen(r)                                # the game's own to-a-Heathen
        self.assertEqual(v.read(r + FACTION, 1), b"\x01")
        v.credit(r, 0)                                   # the next frame's look sees the turning
        return r

    def test_a_former_villager_ages_like_a_believer(self):
        v = Village((FORMER,))
        r = self._converted(v)
        v.credit(r, 4)
        self.assertEqual(v.i32(r, AGE), 605, "the age credit adds their units")
        v.life_tick()
        self.assertEqual(v.i32(r, PROCESSED), 605, "the life tick processes every unit")
        self.assertEqual(v.i32(r, HEALTH), 90, "a Heathen still never eats, starves or loses health")

    def test_a_camp_heathen_and_puzzle_heathens_never_age_with_the_former_row(self):
        v = Village((FORMER,))
        camp = v.villager(1, heathen=True)
        doctor = v.villager(2, heathen=True, role=12)
        chief = v.villager(4, heathen=True, role=13, age=1000)
        for r in (camp, doctor, chief):
            v.credit(r, 7)
            self.assertEqual(v.i32(r, AGE), 600 if r != chief else 1000)
        v.put32(chief + PROCESSED, 900)
        v.life_tick()
        self.assertEqual(v.i32(chief, PROCESSED), 1000, "the stock skip: processed age = age")
        self.assertEqual(v.rand_calls, [])

    def test_a_heathen_who_turned_before_the_row_is_known_by_the_parents_on_the_record(self):
        v = Village((FORMER,))
        r = v.villager(5, heathen=True, parents=True)
        v.credit(r, 3)
        self.assertEqual(v.i32(r, AGE), 603)

    def test_a_record_the_creator_is_filling_is_never_a_former_villager(self):
        # A new record's SetFaith runs to-a-Heathen before any frame has seen it alive.
        v = Village((FORMER,))
        r = v.villager(6, heathen=False)
        v.turn_heathen(r)
        v.credit(r, 3)
        self.assertEqual(v.i32(r, AGE), 600)

    def test_dies_of_old_age_with_a_skeleton_and_is_never_replaced(self):
        v = Village((FORMER, BONES_FORMER))
        r = self._converted(v)
        v.put32(DEATHS_STAT, 17)
        _due_to_die(v, r)
        v.life_tick()
        self.assertEqual((v.i32(r, HEALTH), v.i32(r, CAUSE)), (0, 2), "Old age, by SetHealth")
        self.assertEqual(v.read(r + PRESENT, 1), b"\x01", "the body stays for the believers to bury")
        self.assertEqual(v.u32(DEATHS_STAT), 17, "Heathens never count in the statistics")
        self.assertEqual(v.created, [], "the owner (2026-11-23): a former villager is never replaced")
        self.assertEqual(v.arrived, [])
        self.assertEqual(v.died, [], "a body: the Death record comes at the burial")

    def test_without_a_skeleton_row_nothing_is_left_and_the_death_is_logged(self):
        v = Village((FORMER,))
        r = self._converted(v)
        _due_to_die(v, r)
        v.life_tick()
        self.assertEqual(v.read(r + PRESENT, 1), b"\x00")
        self.assertEqual(v.i32(r, HEALTH), 90, "no body: health untouched, as the game's own removals")
        self.assertEqual(v.stopped[-1], r, "the activity stopped first (the conversion stopped it once too)")
        self.assertEqual(v.died, [(5, 3, 2)], "Death record: Old age, no grave")
        self.assertEqual(v.created, [], "never replaced")

    def test_the_all_heathens_skeleton_row_covers_a_former_villager_too(self):
        v = Village((FORMER, BONES_ALL))
        r = self._converted(v)
        _due_to_die(v, r)
        v.life_tick()
        self.assertEqual(v.read(r + PRESENT, 1), b"\x01")

    def test_no_roll_before_old_age_and_none_between_whole_years(self):
        v = Village((FORMER,))
        r = self._converted(v)
        v.put32(r + PROCESSED, OLD - 40)
        v.put32(r + AGE, OLD + 19)                       # 59 units: one whole year past old age (1,100)
        v.life_tick()
        self.assertEqual(v.i32(r, PROCESSED), OLD + 19)
        self.assertEqual(v.rand_calls, [], "1,100 itself is not past it; 1,120 is the first roll")
        v.put32(r + AGE, OLD + 21)
        v.rand_answers.extend([10])                      # 10 x 1 year over: 10 is not below 10
        v.life_tick()
        self.assertEqual(v.rand_calls, [100])
        self.assertEqual(v.i32(r, HEALTH), 90)


@unittest.skipIf(_skip(), _skip() or "")
class Tribe(unittest.TestCase):
    def test_every_heathen_ages_and_the_camp_one_is_replaced_in_kind(self):
        v = Village((TRIBE,))
        camp = v.villager(1, heathen=True, role=6, orange=1)
        v.villager(9, heathen=True, name="Other")          # another Heathen alive: never from nothing
        v.credit(camp, 2)
        self.assertEqual(v.i32(camp, AGE), 602)
        _due_to_die(v, camp)
        v.life_tick()
        self.assertEqual(v.read(camp + PRESENT, 1), b"\x00", "no skeleton row: nothing left")
        index, args = v.created[0]
        self.assertEqual((args[5], args[6], args[7]), (1, 0, 6), "the same camp role and mask")
        self.assertEqual(args[4], 400)

    def test_old_age_follows_the_villages_medicine_for_camp_heathens_too(self):
        """The believers' threshold, 1,100 + 160 x (Medicine - 1) units, read from the village's own tech level: at
        Medicine 1 a camp Heathen of 1,120 units is rolled for; at Medicine 3 (1,420) not yet; past 1,420 again."""
        for medicine, at, rolled in ((1, OLD + 20, True), (3, OLD + 20, False), (3, OLD + 340, True)):
            with self.subTest(medicine=medicine, at=at):
                v = Village((TRIBE,))
                v.put32(MEDICINE, medicine)
                v.villager(9, heathen=True, name="Other")
                h = v.villager(1, heathen=True, role=4)
                v.put32(h + AGE, at + 1)
                v.put32(h + PROCESSED, at)
                v.rand_answers.extend([0])
                v.life_tick()
                self.assertEqual(v.rand_calls[:1] == [100], rolled)
                self.assertEqual(v.read(h + PRESENT, 1) == b"\x00", rolled, "gone of old age (no skeleton)")
    def test_with_both_aging_rows_there_is_no_double_aging(self):
        v = Village((FORMER, TRIBE))
        r = v.villager(1, heathen=True, parents=True)
        v.credit(r, 3)
        self.assertEqual(v.i32(r, AGE), 603)
        v.life_tick()
        self.assertEqual(v.i32(r, PROCESSED), 603)

    def test_catch_up_processes_every_unit_with_a_roll_each_whole_year(self):
        v = Village((TRIBE,))
        r = v.villager(1, heathen=True, age=OLD + 100)
        v.put32(r + PROCESSED, OLD - 100)
        v.life_tick()                                         # the load-time catch-up: one call, every pass
        self.assertEqual(v.i32(r, PROCESSED), OLD + 100)
        self.assertEqual(v.rand_calls, [100] * 4, "1,120, 1,140, 1,160, 1,180 (1,200 is the last unit's age)")
        self.assertEqual(v.i32(r, HEALTH), 90)

    def test_oldest_villager_never_reads_a_heathen_where_the_statistics_say_so(self):
        v = Village((TRIBE,), statistics_form=True)
        r = v.villager(1, heathen=True, age=1990)
        v.put32(OLDEST_STAT, 10)
        v.credit(r, 10)
        self.assertEqual(v.i32(r, AGE), 2000)
        self.assertEqual(v.u32(OLDEST_STAT), 10)

    def _puzzle_dies(self, role: int, puzzle: int, *, solved: bool, bones: tuple[str, ...] = ()) -> tuple:
        v = Village((TRIBE,) + bones)
        (v.solve if solved else v.unsolve)(puzzle)
        man = v.villager(1, heathen=True, sex=0, name="Kalo")
        r = v.villager(2, heathen=True, role=role, sex=1)
        _due_to_die(v, r)
        v.life_tick()
        return v, r, man

    def test_each_puzzle_heathen_is_replaced_in_the_same_role_while_the_puzzle_is_unsolved(self):
        stock = {12: (2, 70, -1, 400, -14), 14: (3, 90, -1, 540, -74), 15: (4, 90, -1, 540, -74),
                 16: (0, 90, -1, 540, -74), 13: (2, 90, -1, 1000, -94), 17: (1, 70, -1, 400, -25)}
        puzzles = {12: 1, 16: 5, 15: 9, 14: 13, 13: 16, 17: 17}
        for role, (skill, value, sex, age, faith) in stock.items():
            with self.subTest(role=role):
                v, r, man = self._puzzle_dies(role, puzzles[role], solved=False)
                self.assertEqual(len(v.created), 1)
                index, args = v.created[0]
                self.assertEqual(args[:8], [0, skill, value, sex, age, 0, 0, role], "the stock camp's set-up")
                new = v.record(index)
                self.assertEqual(v.i32(new, FAITH), faith)
                if role == 13:
                    self.assertEqual(struct.unpack("<6f", v.read(new + SKILLS, 24)), (100.0,) * 6)
                if role == 17:
                    carrier, cargs = v.conceived[0]
                    self.assertEqual(carrier, new, "the Heathen Mommy comes with her infant")
                    self.assertEqual(v.cstring(cargs[3]), "Kalo", "its other parent a named adult Heathen")
                    self.assertEqual(cargs[6], 1, "forced, as the stock set-up")
                    self.assertNotEqual(v.i32(new, PREGNANT), 0)
                    self.assertEqual(v.u32(TWINS), 0, "no statistics")

    def test_the_new_mommys_other_parent_is_named_of_either_sex_her_family_first(self):
        """The owner, 2026-11-25: "instead of unknown the parents should have names"; villagers are villagers
        regardless of gender.  A living adult Heathen of either sex, never the Mommy, her own family first."""
        cases = (
            ((("Vaihi", 1, 400),), "Vaihi"),                                   # only a woman: she is named
            ((("Tiny Mashudu", 1, 100), ("Kalo Peponi", 0, 400)), "Kalo Peponi"),   # never a child
        )
        for camp, expected in cases:
            with self.subTest(expected=expected):
                v = Village((TRIBE,))
                v.unsolve(17)
                for k, (name, sex, age) in enumerate(camp):
                    v.villager(3 + k, heathen=True, sex=sex, name=name, age=age)
                r = v.villager(2, heathen=True, role=17, sex=0, name="Ahi Mashudu")
                _due_to_die(v, r)
                v.life_tick()
                carrier, cargs = v.conceived[0]
                self.assertEqual(carrier, v.record(v.created[0][0]))
                self.assertEqual(v.cstring(cargs[3]), expected)

    def test_a_solved_puzzles_role_is_never_made_again(self):
        v, r, _ = self._puzzle_dies(13, 16, solved=True)
        self.assertEqual(v.created[0][1][7], 0, "an ordinary Heathen instead")

    def test_a_puzzle_heathens_skeleton_loses_the_role_so_the_finder_finds_the_new_one(self):
        v, r, _ = self._puzzle_dies(12, 1, solved=False, bones=(BONES_ALL,))
        self.assertEqual(v.read(r + PRESENT, 1), b"\x01")
        self.assertEqual(v.i32(r, ROLE), 0)
        self.assertEqual(v.i32(v.record(v.created[0][0]), ROLE), 12)

    def test_the_mommys_infant_is_never_delivered_while_she_is_a_heathen(self):
        v = Village((TRIBE,))
        m = v.villager(1, heathen=True, role=17, sex=1)
        v.put32(m + PREGNANT, 400)
        v.put32(m + LITTER, 1)
        v.put32(m + AGE, 700)
        v.put32(m + PROCESSED, 600)
        v.life_tick()
        self.assertEqual(v.i32(m, PREGNANT), 400)
        self.assertEqual(v.created, [])

    def test_a_full_table_owes_the_replacement_until_there_is_room(self):
        v = Village((TRIBE, BONES_ALL))
        for i in range(150):
            v.villager(i, heathen=True)
        r = v.record(7)
        _due_to_die(v, r)
        v.life_tick()
        self.assertEqual(v.created, [])
        v.write(v.record(40) + PRESENT, b"\x00")
        other = v.record(8)
        v.put32(other + AGE, 601)
        v.life_tick()
        self.assertEqual([i for i, _ in v.created], [40])


@unittest.skipIf(_skip(), _skip() or "")
class Babies(unittest.TestCase):
    def test_the_whole_tribe_shares_one_baby_in_240_units(self):
        # The owner, 2026-11-25: "1 baby every 24 hours across the entire tribe" -- with three women who could
        # conceive, each rolls 1 in 720, so the tribe still has about one baby in 240 units (24 h on Normal).
        v = Village((TRIBE,))
        v.villager(1, heathen=True, sex=0, name="Kalo")
        for i in (2, 3, 4):
            woman = v.villager(i, heathen=True, sex=1, name=f"Mele{i}")
            v.put32(woman + AGE, 601)
        v.rand_answers.extend([1, 1, 1])               # nobody conceives this unit
        v.life_tick()
        self.assertEqual(v.rand_calls[:3], [720, 720, 720])
        self.assertEqual(v.conceived, [])

    def test_a_heathen_couple_has_a_heathen_baby_with_both_parents_recorded(self):
        v = Village((TRIBE,))
        man = v.villager(1, heathen=True, sex=0, name="Kalo")
        woman = v.villager(2, heathen=True, sex=1, name="Mele")
        v.put32(man + HEAD, 10)
        v.put32(woman + HEAD, 20)
        v.put32(woman + AGE, 601)
        v.rand_answers.extend([0, 0])                  # conceive (1 in 240 x 1 woman), pick the man
        v.life_tick()
        self.assertEqual(v.rand_calls[0], 240, "the owner (2026-11-25): one baby a tribe in 240 units (24 h)")
        self.assertEqual(len(v.conceived), 1)
        carrier, args = v.conceived[0]
        self.assertEqual((carrier, v.cstring(args[3]), args[6]), (woman, "Kalo", 1))
        self.assertEqual(v.u32(TWINS), 0, "the statistics' twins put back")
        conceived_at = v.i32(woman, PREGNANT)
        v.put32(woman + AGE, conceived_at + 40)
        v.life_tick()
        self.assertEqual(v.created, [], "not yet: the birth is 40 units after conception, as a believer's")
        v.put32(woman + AGE, conceived_at + 42)
        v.rand_answers.extend([0, 0, 1])               # the baby's Faith, the head roll (95%), head +-1
        v.life_tick()
        self.assertEqual(len(v.created), 1)
        index, cargs = v.created[0]
        baby = v.record(index)
        self.assertEqual(cargs[4], 40, "born at 40 units, as the stock birth")
        self.assertEqual(v.read(baby + FACTION, 1), b"\x01", "a Heathen")
        self.assertEqual(v.cstring(baby + FATHER_NAME), "Kalo")
        self.assertEqual(v.cstring(baby + MOTHER_NAME), "Mele")
        self.assertEqual((v.i32(baby, FATHER_HEAD), v.i32(baby, MOTHER_HEAD)), (10, 20))
        self.assertEqual(v.i32(baby, HEAD), 15)
        self.assertEqual(v.i32(woman, PREGNANT), 0)
        self.assertEqual(v.arrived, [], "a birth is never an Arrived record")
        # The owner, 2026-11-22: the logs record the Heathens too.  The Cause of Death companion is told it is a
        # birth (never an arrival), and the Births log writes its Birth record (marked a Heathen by that DLL), the
        # parents from the baby's own record, the name handed over (no believers' last-name rule), one baby.
        self.assertEqual(v.noted, [baby], "the Cause of Death companion told: a birth")
        self.assertEqual(len(v.births), 1)
        name, bargs = v.births[0]
        self.assertEqual(name, v.cstring(baby + NAME))
        self.assertEqual(bargs[0], 5)
        self.assertEqual((bargs[2], bargs[4], bargs[7], bargs[10], bargs[11]), (15, 0, 0, baby, 1),
                         "the child's head, no parents given (read from the record), the record, one baby")

    def test_a_birth_waits_until_the_villages_reserve_stays_free(self):
        # Codex (#850): delivery keeps HA_ROOM_KEPT (10) records free for the village's own births, as conception does.
        v = Village((TRIBE,))
        man = v.villager(1, heathen=True, sex=0, name="Kalo")
        woman = v.villager(2, heathen=True, sex=1, name="Mele")
        v.put32(woman + AGE, 601)
        v.rand_answers.extend([0, 0])
        v.life_tick()
        self.assertEqual(len(v.conceived), 1)
        for i in [0] + list(range(3, 140)):              # 10 records free: the baby would leave only 9
            v.villager(i, heathen=False)
        conceived = v.i32(woman, PREGNANT)
        v.put32(woman + AGE, conceived + 42)
        v.life_tick()
        self.assertEqual(v.created, [], "deferred: the believers' reserve stays")
        self.assertEqual(v.i32(woman, PREGNANT), conceived, "the pregnancy kept")
        v.write(v.record(139) + PRESENT, b"\x00")        # one more free: 11
        v.put32(woman + AGE, conceived + 43)
        v.life_tick()
        self.assertEqual(len(v.created), 1, "born once the reserve stays free")
        _ = man
    def test_no_babies_with_the_former_row_alone_or_without_a_man(self):
        for flags, with_man in (((FORMER,), True), ((TRIBE,), False)):
            with self.subTest(flags=flags, man=with_man):
                v = Village(flags)
                if with_man:
                    v.villager(1, heathen=True, sex=0, parents=True)
                woman = v.villager(2, heathen=True, sex=1, parents=True)
                v.put32(woman + AGE, 601)
                v.rand_answers.extend([0, 0])
                v.life_tick()
                self.assertEqual(v.conceived, [])

    def test_a_pregnancy_from_before_she_turned_heathen_waits_for_her_to_rejoin(self):
        v = Village((TRIBE,))
        woman = v.villager(2, heathen=True, sex=1)
        v.put32(woman + PREGNANT, 500)
        v.put32(woman + LITTER, 1)
        v.put32(woman + PROCESSED, 600)
        v.put32(woman + AGE, 601)
        v.life_tick()
        self.assertEqual(v.i32(woman, PREGNANT), 500)
        self.assertEqual(v.created, [])


ROSTER, ROSTER_STRIDE = 0x5481A8, 0x5C


@unittest.skipIf(_skip(), _skip() or "")
class GravesAndStartOver(unittest.TestCase):
    """Heathens never count: a Heathen's grave is written down for the Village Statistics' Village Elders
    (VvfpHeathenAgingGrave), and Start Over (VvfpHeathenAgingVillageReset, from VVFP Save Reset.dll) forgets the
    village's former villagers and graves."""

    def _bury(self, v: Village, record: int, entry: int) -> None:
        """The burial step 0x473F50: the presence byte cleared, then the Roster of the Dead writer's entry (name +0,
        age +0x1C) in the first free place."""
        v.write(record + PRESENT, b"\x00")
        at = ROSTER + entry * ROSTER_STRIDE
        v.write(at, v.read(record + NAME, 0x19))
        v.put32(at + 0x1C, v.u32(record + AGE))

    def test_a_buried_heathens_grave_is_written_down_and_a_believers_is_not(self):
        v = Village((TRIBE, BONES_ALL))
        believer = v.villager(9, heathen=False, name="Ana")
        v.put32(ROSTER + 0x1C, 700)                     # an older believer's grave in entry 0
        v.write(ROSTER, b"Old Believer\0")
        h = v.villager(1, heathen=True, role=13, name="Mojo Mahuru")
        _due_to_die(v, h)
        v.life_tick()
        self.assertEqual(v.i32(h, HEALTH), 0, "a skeleton")
        v.credit(believer, 1)                           # the watch sees the body lying
        self._bury(v, h, 1)
        v.credit(believer, 1)                           # ...and then its grave
        self.assertEqual(v.export("VvfpHeathenAgingGrave", 5, 1), 1, "the Heathen's grave")
        self.assertEqual(v.export("VvfpHeathenAgingGrave", 5, 0), 0, "a believer's grave")
        self.assertEqual(v.export("VvfpHeathenAgingGrave", 4, 1), 0, "another game")

    def test_a_save_right_after_the_burial_already_knows_the_grave(self):
        # Codex (#850): the Village Statistics ask at the save, before the throttled look has seen the burial.
        v = Village((TRIBE, BONES_ALL))
        believer = v.villager(9, heathen=False, name="Ana")
        v.villager(8, heathen=True, name="Other")
        h = v.villager(1, heathen=True, role=4, name="Old One")
        _due_to_die(v, h)
        v.life_tick()
        v.credit(believer, 1)                           # the body watched
        self._bury(v, h, 0)
        self.assertEqual(v.export("VvfpHeathenAgingGrave", 5, 0), 1, "no age credit in between")
    def test_an_unburied_body_the_game_removes_leaves_no_grave(self):
        v = Village((TRIBE, BONES_ALL))
        believer = v.villager(9, heathen=False)
        h = v.villager(1, heathen=True)
        _due_to_die(v, h)
        v.life_tick()
        v.credit(believer, 1)
        v.write(h + PRESENT, b"\x00")                   # the 240-unit removal: no Roster entry
        v.credit(believer, 1)
        self.assertEqual(v.export("VvfpHeathenAgingGrave", 5, 0), 0)

    def test_start_over_forgets_the_former_villagers_and_graves(self):
        v = Village((FORMER, BONES_ALL))
        r = v.villager(3, heathen=False)
        v.credit(r, 1)
        v.turn_heathen(r)
        v.credit(r, 2)
        self.assertEqual(v.i32(r, AGE), 603, "a former villager ages")
        v.export("VvfpHeathenAgingVillageReset", 5, 1)
        v.credit(r, 2)
        self.assertEqual(v.i32(r, AGE), 603, "forgotten at Start Over: the new village's Heathen never was ours")
        v.export("VvfpHeathenAgingVillageReset", 4, 1)  # another game: nothing

SAVE_MANAGER_WORD, SLOT_FIELD = 0x4DACE0, 0x17D80


@unittest.skipIf(_skip(), _skip() or "")
class OwedReplacements(unittest.TestCase):
    """A replacement owed while the table is full (Codex, #850): made as soon as there is room, whether or not any
    Heathen ages then, and only in the village it is owed to (kept per save slot across a Change Tribe)."""

    def _full_with_one_former(self, v: Village) -> int:
        """A full table of camp Heathens (none with an age unit due) and one camp Heathen dying of old age."""
        for i in range(150):
            v.villager(i, heathen=True)
        dying = v.villager(7, heathen=True, role=3, name="Tane")
        _due_to_die(v, dying)
        v.life_tick()
        self.assertEqual(v.i32(dying, HEALTH), 0, "a skeleton keeps the table full")
        self.assertEqual(v.created, [], "owed: no room")
        return dying

    def _slot(self, v: Village, slot: int) -> None:
        if not getattr(v, "save_manager", 0):
            v.save_manager = v.alloc(SLOT_FIELD + 0x10)
            v.put32(SAVE_MANAGER_WORD, v.save_manager)
        v.put32(v.save_manager + SLOT_FIELD, slot)

    def test_paid_when_room_comes_though_no_heathen_ages(self):
        v = Village((TRIBE, BONES_ALL))
        self._full_with_one_former(v)
        v.write(v.record(40) + PRESENT, b"\x00")        # room at last
        v.credit(v.record(41), 1)                        # a camp Heathen's age credit: it does not age
        self.assertEqual([i for i, _ in v.created], [40])

    def test_a_change_of_tribe_never_takes_the_owed_replacement_along(self):
        v = Village((TRIBE, BONES_ALL))
        self._slot(v, 1)
        v.credit(v.record(0), 0)                         # village 1 is the one in play
        self._full_with_one_former(v)
        self._slot(v, 2)                                 # Change Tribe: village 2, with room
        v.write(v.record(40) + PRESENT, b"\x00")
        v.credit(v.record(41), 1)
        self.assertEqual(v.created, [], "village 1's replacement is never made in village 2")
        self._slot(v, 1)                                 # back to village 1
        v.credit(v.record(41), 1)
        self.assertEqual([i for i, _ in v.created], [40], "...and still owed there")

    def test_start_over_drops_that_villages_owed_replacement(self):
        v = Village((TRIBE, BONES_ALL))
        self._slot(v, 3)
        v.credit(v.record(0), 0)
        self._full_with_one_former(v)
        v.export("VvfpHeathenAgingVillageReset", 5, 3)
        v.write(v.record(40) + PRESENT, b"\x00")
        v.credit(v.record(41), 1)
        self.assertEqual(v.created, [])

DISLIKES = 0x1F68


@unittest.skipIf(_skip(), _skip() or "")
class SelfReview(unittest.TestCase):
    """#850's self-review: turnings seen by the age credit (no call-site splices), a stale expecting entry, entries
    following their villager, and the stock camp's Faith for a replacement."""

    def _seen_then(self, v: Village, index: int = 3, **kw) -> int:
        r = v.villager(index, heathen=False, **kw)
        v.credit(r, 1)
        return r

    def test_a_turning_by_the_direct_faction_setter_is_seen(self):
        # The Spa's and The Cracked Mask's own `call 0x466880` (faction 1), not through to-a-Heathen.
        v = Village((FORMER,))
        self.assertEqual(v.installed, 1)
        r = self._seen_then(v)
        v.write(r + FACTION, b"\x01")
        v.credit(r, 3)
        self.assertEqual(v.i32(r, AGE), 604, "a former villager: ages from that very credit")

    def test_no_call_site_of_the_spa_cracked_mask_or_to_a_heathen_is_written(self):
        v = Village((FORMER, TRIBE))
        image = v.image()
        stock = Village(())                              # not installed
        base = v.exe_base
        for va, n in ((0x415D0C, 5), (0x416C5B, 5), (0x4669E0, 5), (0x4669F5, 10), (0x466966, 7), (0x41699F, 5)):
            with self.subTest(va=hex(va)):
                self.assertEqual(image[va - base:va - base + n], stock.image()[va - base:va - base + n])

    def test_a_stale_expecting_entry_never_delivers_a_believer_pregnancy_among_the_heathens(self):
        v = Village((TRIBE,))
        man = v.villager(1, heathen=True, sex=0, name="Kalo")
        woman = v.villager(2, heathen=True, sex=1, name="Mele")
        v.put32(woman + AGE, 601)
        v.rand_answers.extend([0, 0])
        v.life_tick()                                    # a Heathen pregnancy: expecting
        self.assertEqual(len(v.conceived), 1)
        v.write(woman + FACTION, b"\x00")                # she joins the tribe ...
        v.credit(woman, 0)                               # ... and is seen a believer
        v.put32(woman + PREGNANT, 0)                     # her baby born a believer
        v.put32(woman + PREGNANT, 700)                   # later, a believer pregnancy
        v.put32(woman + LITTER, 1)
        v.write(woman + FACTION, b"\x01")                # and she turns Heathen while expecting
        v.put32(woman + PROCESSED, 760)
        v.put32(woman + AGE, 770)
        v.life_tick()
        self.assertEqual(v.created, [], "her believer pregnancy waits for her to rejoin, as in the stock game")
        self.assertEqual(v.i32(woman, PREGNANT), 700)
        _ = man

    def test_a_parentless_founder_whose_likes_change_as_she_turns_heathen_is_still_a_former_villager(self):
        # Codex (#850): a Custom Island Event changes her dislikes, then makes her a Heathen, before the next look.
        v = Village((FORMER,))
        r = self._seen_then(v, name="Founder")           # no parents: only the turning says she was ours
        v.write(r + DISLIKES, struct.pack("<3I", 9, 9, 9))
        v.write(r + FACTION, b"\x01")
        v.credit(r, 1)
        v.credit(r, 1)
        self.assertEqual(v.i32(r, AGE), 603, "seen turning under her new identity: she ages")
    def test_a_former_villager_whose_dislikes_change_in_place_still_ages(self):
        v = Village((FORMER,))
        r = self._seen_then(v)
        v.write(r + FACTION, b"\x01")
        v.credit(r, 1)                                   # noted
        self.assertEqual(v.i32(r, AGE), 602)
        v.write(r + DISLIKES, struct.pack("<3I", 9, 9, 9))   # an island event changes her dislikes
        v.credit(r, 1)                                   # the look that follows her
        v.credit(r, 1)
        self.assertEqual(v.i32(r, AGE), 604, "the entry followed her new identity")

    def test_a_renamed_former_villager_still_ages(self):
        v = Village((FORMER,))
        r = self._seen_then(v)
        v.write(r + FACTION, b"\x01")
        v.credit(r, 1)
        v.write(r + NAME, b"V3 Akikai\0")                # a last name given
        v.credit(r, 1)
        v.credit(r, 1)
        self.assertEqual(v.i32(r, AGE), 604)

    def test_without_the_follow_a_changed_identity_is_a_stranger(self):
        # The control: a different villager (sex changed too) in the record is not followed.
        v = Village((FORMER,))
        r = self._seen_then(v)
        v.write(r + FACTION, b"\x01")
        v.credit(r, 1)
        v.write(r + NAME, b"Somebody\0")
        v.put32(r + SEX, 1)
        v.write(r + DISLIKES, struct.pack("<3I", 9, 9, 9))
        v.credit(r, 1)
        v.credit(r, 1)
        self.assertEqual(v.i32(r, AGE), 602)

    def test_a_replacement_keeps_one_of_the_five_easy_camp_faiths(self):
        for faith, keeps in ((-9, True), (-30, True), (-50, False)):
            with self.subTest(faith=faith):
                v = Village((TRIBE,))
                h = v.villager(1, heathen=True, role=2)
                v.villager(9, heathen=True, name="Other")      # another Heathen alive: never from nothing
                v.put32(h + FAITH, faith & 0xFFFFFFFF)
                _due_to_die(v, h)
                v.life_tick()
                new = v.record(v.created[0][0])
                got = v.i32(new, FAITH)
                if keeps:
                    self.assertEqual(got, faith)
                else:
                    self.assertTrue(-67 <= got <= -38, got)


class OfflineRenames(unittest.TestCase):
    def test_the_time_warp_asks_which_heathens_age(self):
        # The Origins Time Warp writes ages past the age credit and asks this (tests/test_vv5_time_warp_ages_heathens.py).
        if _skip():
            self.skipTest(_skip())
        v = Village((FORMER,))
        former = v.villager(1, heathen=True, parents=True)
        camp = v.villager(2, heathen=True)
        believer = v.villager(3, heathen=False)
        self.assertEqual([v.export("VvfpHeathenAgingAges", r) for r in (former, camp, believer)], [1, 0, 0])
        tribe = Village((TRIBE,))
        camp = tribe.villager(2, heathen=True)
        self.assertEqual(tribe.export("VvfpHeathenAgingAges", camp), 1, "the tribe row ages every Heathen")
        self.assertEqual(Village(()).export("VvfpHeathenAgingAges", camp), 0, "not installed: none")

    def test_a_moved_slots_file_is_retagged_and_read_there(self):
        # Codex (#850): Copy / Move Player Slot retag the file's slot (offset 16) through vv_copy_slot, so the
        # companion accepts it in the new slot.
        if _skip():
            self.skipTest(_skip())
        import vv_copy_slot
        v = Village((FORMER,))
        OwedReplacements._slot(None, v, 3)
        r = v.villager(1, heathen=True, name="Moved")       # no parents: only the file says she left the tribe
        made = (struct.pack("<5I", 0x31414856, 2, 5, 1, 1) + struct.pack("<II", _identity(v, r), 1))
        moved = vv_copy_slot.transform_binary(made, 1, 3, {}, "Tribe", "Tribe")
        self.assertEqual(struct.unpack_from("<I", moved, 16)[0], 3, "the slot field retagged")
        self.assertEqual(moved[:16] + moved[20:], made[:16] + made[20:], "nothing else changed")
        path = "C:\\Docs\\LDW\\Game\\Virtual Villagers Fun Patcher\\Save 3\\Data\\Heathen Aging\\Heathen Aging - Save 3.dat"
        v.files[path] = moved
        v.credit(r, 1)
        v.credit(r, 1)
        self.assertEqual(v.i32(r, AGE), 602, "read in the new slot: a former villager who ages")
    def test_the_rename_planner_rekeys_the_heathen_aging_file(self):
        import tempfile
        import inspect
        import vv_last_names as ln
        src = inspect.getsource(ln.plan_renames)
        self.assertIn('"Heathen Aging", f"Heathen Aging - Save {slot}.dat"', src)
        self.assertIn('b"VHA1", {2: 8}, game, 20, 0, title_map', src)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "Heathen Aging - Save 1.dat"
            original = (struct.pack("<5I", 0x31414856, 2, 5, 3, 1)
                        + struct.pack("<6I", 0xAAAA0001, 1, 0xAAAA0001, 2, 7, 3))
            path.write_bytes(original)
            plan = ln.Plan({}) if hasattr(ln, "Plan") else None
            if plan is None:
                self.skipTest("no Plan in vv_last_names")
            ln._plan_u32_file(plan, path, b"VHA1", {2: 8}, 5, 20, 0, {0xAAAA0001: 0xBBBB0002}, "Heathen Aging", {})
            self.assertEqual(len(plan.changes), 1)
            after = plan.changes[0].updated
            self.assertEqual(struct.unpack_from("<6I", after, 20), (0xBBBB0002, 1, 0xBBBB0002, 2, 7, 3),
                             "former and expecting carried; the grave entry 7 left alone")

@unittest.skipIf(_skip(), _skip() or "")
class OnlyCampHeathensAreReplaced(unittest.TestCase):
    """The owner (2026-11-23): only camp Heathens (and puzzle Heathens while their puzzle is unsolved) are replaced;
    once The Last Heathen (puzzle 25) is solved nobody is, and no new Heathen baby is conceived."""

    def test_a_camp_heathen_is_replaced_and_a_former_villager_is_not(self):
        v = Village((TRIBE,))
        camp = v.villager(1, heathen=True, role=4)
        former = v.villager(2, heathen=True, parents=True)
        _due_to_die(v, camp)
        _due_to_die(v, former)
        v.life_tick()
        self.assertEqual(len(v.created), 1, "the camp Heathen's replacement only")
        self.assertEqual(v.created[0][1][7], 4)

    def test_a_former_villager_in_a_puzzle_role_is_still_replaced_in_that_role(self):
        v = Village((FORMER,))
        r = v.villager(2, heathen=True, parents=True, role=12)
        v.villager(9, heathen=True, name="Other")          # another Heathen alive: never from nothing
        _due_to_die(v, r)
        v.life_tick()
        self.assertEqual([a[7] for _, a in v.created], [12], "the puzzle keeps working")

    def test_after_the_last_heathen_nobody_is_replaced(self):
        for role, puzzle in ((4, None), (13, 16), (17, 17)):
            with self.subTest(role=role):
                v = Village((TRIBE,))
                v.solve(25)
                h = v.villager(1, heathen=True, role=role)
                _due_to_die(v, h)
                v.life_tick()
                self.assertEqual(v.created, [])
                self.assertEqual(v.read(h + PRESENT, 1), b"\x00", "gone: the camp empties")

    def test_an_owed_replacement_is_dropped_once_the_last_heathen_is_solved(self):
        v = Village((TRIBE, BONES_ALL))
        for i in range(150):
            v.villager(i, heathen=True)
        dying = v.villager(7, heathen=True, role=3)
        _due_to_die(v, dying)
        v.life_tick()
        self.assertEqual(v.created, [])
        v.solve(25)
        v.write(v.record(40) + PRESENT, b"\x00")
        v.credit(v.record(41), 1)
        v.unsolve(25)                                    # (never happens in the game: proves it was dropped)
        v.credit(v.record(41), 1)
        self.assertEqual(v.created, [])

    def test_no_heathen_baby_is_conceived_after_the_last_heathen(self):
        v = Village((TRIBE,))
        v.solve(25)
        v.villager(1, heathen=True, sex=0)
        woman = v.villager(2, heathen=True, sex=1)
        v.put32(woman + AGE, 601)
        v.rand_answers.extend([0, 0])
        v.life_tick()
        self.assertEqual(v.conceived, [])


@unittest.skipIf(_skip(), _skip() or "")
class NeverFromNothing(unittest.TestCase):
    """The owner (2026-11-23): with no Heathen alive this companion never makes one, and after The Last Heathen it
    makes none at all -- no replacement, no birth (a pregnancy conceived before waits, never delivered among the
    Heathens)."""

    def test_the_last_heathen_alive_dying_is_not_replaced(self):
        for role in (4, 13):
            with self.subTest(role=role):
                v = Village((TRIBE,))
                h = v.villager(1, heathen=True, role=role)
                _due_to_die(v, h)
                v.life_tick()
                self.assertEqual(v.created, [])

    def test_an_owed_replacement_is_never_made_once_no_heathen_is_alive(self):
        v = Village((TRIBE, BONES_ALL))
        for i in range(150):
            v.villager(i, heathen=False)                # believers fill the table
        h = v.villager(7, heathen=True, role=3)
        other = v.villager(8, heathen=True, role=3)
        _due_to_die(v, h)
        v.life_tick()
        self.assertEqual(v.created, [], "owed")
        v.write(other + PRESENT, b"\x00")             # the other Heathen gone too
        v.write(v.record(40) + PRESENT, b"\x00")
        v.credit(v.record(41), 1)
        self.assertEqual(v.created, [])

    def test_no_birth_after_the_last_heathen(self):
        v = Village((TRIBE,))
        v.villager(1, heathen=True, sex=0, name="Kalo")
        woman = v.villager(2, heathen=True, sex=1, name="Mele")
        v.put32(woman + AGE, 601)
        v.rand_answers.extend([0, 0])
        v.life_tick()
        self.assertEqual(len(v.conceived), 1)
        v.solve(25)
        conceived = v.i32(woman, PREGNANT)
        v.put32(woman + AGE, conceived + 60)
        v.life_tick()
        self.assertEqual(v.created, [], "no Heathen baby after The Last Heathen")
        self.assertEqual(v.i32(woman, PREGNANT), conceived, "the pregnancy waits, as in the stock game")


@unittest.skipIf(_skip(), _skip() or "")
class CodexQueueAndBodies(unittest.TestCase):
    """Codex (#850): more than 32 owed replacements, each keeping its Faith, kept in the village's own file; more
    than 32 Heathen bodies watched for their graves."""

    def _many_die(self, v: Village, n: int, faith: int = -50) -> list[int]:
        for i in range(150):
            v.villager(i, heathen=True)
        dying = []
        for i in range(10, 10 + n):
            r = v.record(i)
            v.put32(r + ROLE, 3)
            v.put32(r + FAITH, faith & 0xFFFFFFFF)
            _due_to_die(v, r)
            dying.append(r)
        v.rand_answers.clear()
        v.rand_answers.extend([0] * 1000)              # every roll takes them (and every other draw is 0)
        v.life_tick()
        return dying

    def test_forty_owed_replacements_are_all_made_each_with_its_faith(self):
        v = Village((TRIBE, BONES_ALL))
        self._many_die(v, 40, faith=-9)
        self.assertEqual(v.created, [], "a full table: all owed")
        for i in range(100, 140):
            v.write(v.record(i) + PRESENT, b"\x00")
        v.credit(v.record(5), 1)
        self.assertEqual(len(v.created), 40)
        self.assertEqual({v.i32(v.record(i), FAITH) for i, _ in v.created}, {-9}, "the easy Faith kept while owed")

    def test_forty_buried_heathens_all_have_their_graves_written_down(self):
        v = Village((TRIBE, BONES_ALL))
        dying = self._many_die(v, 40)
        v.credit(v.record(5), 1)                       # every body watched
        for entry, r in enumerate(dying):
            at = ROSTER + entry * ROSTER_STRIDE
            v.write(r + PRESENT, b"\x00")
            v.write(at, v.read(r + NAME, 0x19))
            v.put32(at + 0x1C, v.u32(r + AGE))
        v.credit(v.record(5), 1)
        self.assertEqual(sum(v.export("VvfpHeathenAgingGrave", 5, e) for e in range(40)), 40)

def _identity(v: Village, record: int) -> int:
    """native/shared/custom_titles.h vv_title_identity: the name (0x19), the likes and dislikes (3 dwords each)."""
    h = 2166136261
    for b in v.read(record + NAME, 0x19).split(b"\0")[0]:
        h = ((h ^ b) * 16777619) & 0xFFFFFFFF
    h = ((h ^ 0xFF) * 16777619) & 0xFFFFFFFF
    for b in v.read(record + LIKES, 12) + v.read(record + DISLIKES, 12):
        h = ((h ^ b) * 16777619) & 0xFFFFFFFF
    return h or 1


@unittest.skipIf(_skip(), _skip() or "")
class AFullFile(unittest.TestCase):
    """Codex (#850): a full file never loses a living villager's entry -- the entries of villagers no longer in the
    village are pruned first."""

    def test_a_full_file_prunes_the_gone_and_keeps_the_living(self):
        v = Village((FORMER,))
        OwedReplacements._slot(None, v, 1)
        born = v.villager(1, heathen=True, parents=True, name="Born Here")   # born a Heathen (the file says so)
        path = "C:\\Docs\\LDW\\Game\\Virtual Villagers Fun Patcher\\Save 1\\Data\\Heathen Aging\\Heathen Aging - Save 1.dat"
        entries = [(_identity(v, born), 0)] + [(0x10000 + k, 1) for k in range(2047)]   # the oldest is the living one
        v.files[path] = (struct.pack("<5I", 0x31414856, 2, 5, len(entries), 1)
                         + b"".join(struct.pack("<II", who, kind) for who, kind in entries))
        v.credit(born, 1)                                # the file read
        self.assertEqual(v.i32(born, AGE), 600, "born a Heathen: not a former villager")
        r = v.villager(3, heathen=False, name="Leaver")
        v.credit(r, 1)
        v.write(r + FACTION, b"\x01")                    # turns Heathen: a new entry into a full list
        v.credit(r, 1)
        v.credit(r, 1)
        self.assertEqual(v.i32(r, AGE), 603, "the new former villager is written down")
        v.credit(born, 1)
        self.assertEqual(v.i32(born, AGE), 600, "...and the living born Heathen's entry was kept")
        data = v.files.get(path, b"")
        count = struct.unpack_from("<I", data, 12)[0]
        kept = [struct.unpack_from("<II", data, 20 + 8 * k) for k in range(count)]
        self.assertIn((_identity(v, born), 0), kept)
        self.assertLess(count, 2048, "the gone villagers' entries pruned")

ROWS = {
    "vv5_former_villagers_keep_aging": ("Former Villagers Keep Aging Among the Heathens", FORMER, True),
    "vv5_heathen_tribe_ages": ("Heathen Tribe Ages, Dies and Has Children", TRIBE, True),
    "vv5_former_villager_heathens_leave_skeletons": ("Former Villagers Among the Heathens Leave Skeletons",
                                                     BONES_FORMER, False),
    "vv5_all_heathens_leave_skeletons": ("All Heathens Leave Skeletons", BONES_ALL, False),
}


class TheRows(unittest.TestCase):
    def test_registered_bundled_documented(self):
        import patcher_files
        import vv_fun_patcher as patcher
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        guide = json.loads((ROOT / "data" / "how_to_use.json").read_text(encoding="utf-8"))
        how_to = (ROOT / "How to Use.txt").read_text(encoding="utf-8")
        log = (ROOT / "docs" / "transparency-log.md").read_text(encoding="utf-8")
        ids = {p.id for p in patcher.load_public_fun_patches()}
        self.assertEqual(patcher.STARTUP_LOADER_COMPANIONS_3.index("VVFP Heathen Aging.dll"), 15)
        self.assertIn('"VVFP Heathen Aging.dll"',
                      (ROOT / "native" / "shared" / "startup_companions_3.h").read_text(encoding="utf-8"))
        self.assertIn('"assets/heathen_aging/VVFP Heathen Aging.dll"', release)
        for row_id, (name, flag, ships_dll) in ROWS.items():
            with self.subTest(row_id):
                row = json.loads((ROOT / "data" / f"{row_id}_feature.json").read_text(encoding="utf-8"))
                self.assertEqual((row["id"], row["name"], row["game_id"]), (row_id, name, "vv5"))
                self.assertIn(row_id, ids)
                dests = [c["destination"] for c in row["companion_files"]]
                self.assertEqual(dests, (["VVFP Heathen Aging.dll"] if ships_dll else []) + [flag])
                self.assertIn(flag, patcher_files.PATCHER_READS)
                self.assertIn(f'"assets/heathen_aging/{flag}"', release)
                self.assertIn(f'"data/{row_id}_feature.json"', release)
                self.assertIn(f"- Patch ID: `{row_id}`", readme)
                self.assertIn(row["description"], readme)
                self.assertIn(f"{name.upper()} (NEW BELIEVERS)", how_to)
                self.assertIn(f"#### {name} (`{row_id}`)", log)
                entry = [e for e in guide["patches"] if row_id in e.get("ids", [])]
                self.assertEqual(len(entry), 1)
                if not ships_dll:
                    self.assertIn("**Only matters with", row["description"], "the dependency, in bold")
        bones_former = json.loads((ROOT / "data" / "vv5_former_villager_heathens_leave_skeletons_feature.json")
                                  .read_text(encoding="utf-8"))
        bones_all = json.loads((ROOT / "data" / "vv5_all_heathens_leave_skeletons_feature.json")
                               .read_text(encoding="utf-8"))
        self.assertEqual(bones_former["conflicts"], ["vv5_all_heathens_leave_skeletons"])
        self.assertEqual(bones_all["conflicts"], ["vv5_former_villager_heathens_leave_skeletons"])

    def test_no_other_new_believers_row_writes_a_byte_this_companion_writes(self):
        """Two companions splicing one site with all-or-none stock-byte checks: the second installs nothing (the
        self-review of #850: Heathens Keep Their Masks, #843, splices The Spa's and The Cracked Mask's calls and
        0x4669F5).  Every VV5 row's declared run-time sites -- and #843's, from its branch when it is fetched --
        are checked against this companion's two."""
        import subprocess

        def ranges(row):
            return [(int(d["va"], 16), int(d["va"], 16) + len(d["stock_bytes"]) // 2) for d in row.get("runtime_detours", [])]

        mine = ranges(json.loads((ROOT / "data" / "vv5_heathen_tribe_ages_feature.json").read_text(encoding="utf-8")))
        self.assertEqual(sorted(a for a, _ in mine), [0x470077, 0x472CB7])
        others = {}
        for path in (ROOT / "data").glob("vv5_*_feature.json"):
            # (Heathens can be selected in Island Events ships this very companion: its sites are these two)
            if path.name in {f"{r}_feature.json" for r in ROWS} | {"vv5_heathens_in_island_events_feature.json"}:
                continue
            others[path.name] = ranges(json.loads(path.read_text(encoding="utf-8")))
        shown = subprocess.run(["git", "show", "origin/feat/98-reverted-heathens-keep-mask-look:"
                                "data/vv5_heathens_keep_masks_feature.json"], cwd=ROOT, capture_output=True)
        if shown.returncode == 0:
            others["#843 Keep Masks"] = ranges(json.loads(shown.stdout.decode("utf-8-sig")))
        for name, spans in others.items():
            for a, b in spans:
                for c, d in mine:
                    with self.subTest(row=name, va=hex(a)):
                        self.assertTrue(b <= c or d <= a, f"{name} writes 0x{a:X}..0x{b:X}")
    def test_the_dll_exports_and_the_flag_files(self):
        try:
            import pefile
        except ImportError:
            self.skipTest("pefile is not installed")
        pe = pefile.PE(str(DLL))
        names = sorted(e.name.decode() for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name)
        self.assertEqual(names, ["VvfpHeathenAgingAges", "VvfpHeathenAgingCoupleOf", "VvfpHeathenAgingEventGone",
                                 "VvfpHeathenAgingEventPregnancy", "VvfpHeathenAgingEvolution",
                                 "VvfpHeathenAgingGrave", "VvfpHeathenAgingInstalled", "VvfpHeathenAgingVillageReset",
                                 "VvfpStartup"])
        for _, (name, flag, _) in ROWS.items():
            text = (ROOT / "assets" / "heathen_aging" / flag).read_bytes()
            self.assertTrue(text.startswith(f'Virtual Villagers Fun Patcher: "{name}" (New Believers).\n'.encode()))
            self.assertNotIn(b"\r", text)


EVENTS = "VVFP Heathen Aging Events.txt"


@unittest.skipIf(_skip(), _skip() or "")
class IslandEvents(unittest.TestCase):
    """"Heathens can be selected in Island Events/Heathen-Exclusive Events" (the owner, 2026-11-23: "Heathens CAN die,
    vanish and get pregnant from events"): the Story engine hands an event's death, disappearance or pregnancy of an
    ordinary Heathen to this companion (VvfpHeathenAgingEventGone / VvfpHeathenAgingEventPregnancy), which follows the
    Heathens' own rules -- with no aging row ticked too."""

    def test_the_events_flag_alone_installs_and_nobody_ages(self):
        v = Village((EVENTS,))
        self.assertEqual(v.installed, 1)
        camp = v.villager(1, heathen=True)
        v.credit(camp, 3)
        self.assertEqual(v.i32(camp, AGE), 600, "no aging row: a Heathen still never ages")

    def test_without_the_events_flag_the_exports_do_nothing(self):
        v = Village((TRIBE,))
        v.villager(1, heathen=True)
        v.villager(9, heathen=True)
        self.assertEqual(v.export("VvfpHeathenAgingEventGone", 5, 1, 0, 5), 0)
        self.assertEqual(v.read(v.record(1) + PRESENT, 1), b"\x01")

    def test_a_death_leaves_nothing_is_logged_and_the_camp_heathen_is_replaced(self):
        v = Village((EVENTS,))
        camp = v.villager(1, heathen=True, role=4, red=1)
        v.villager(9, heathen=True, name="Other")
        v.put32(DEATHS_STAT, 7)
        self.assertEqual(v.export("VvfpHeathenAgingEventGone", 5, 1, 0, 5), 1)
        self.assertEqual(v.read(camp + PRESENT, 1), b"\x00", "no skeleton row: nothing left")
        self.assertEqual(v.i32(camp, HEALTH), 90)
        self.assertEqual(v.died, [(5, 1, 5)], "a Death record, the event's cause (Cause of Death's 5), no grave")
        self.assertEqual(v.u32(DEATHS_STAT), 7, "never counted")
        index, args = v.created[0]
        self.assertEqual((args[6], args[7]), (1, 4), "the same camp role and mask")
        self.assertEqual(v.arrived[-1], (index, "Replaced a Heathen lost in an island event"))

    def test_with_a_skeleton_row_a_body_is_left_and_the_statistics_put_back(self):
        v = Village((EVENTS, BONES_ALL))
        camp = v.villager(1, heathen=True)
        v.villager(9, heathen=True)
        v.put32(DEATHS_STAT, 7)
        self.assertEqual(v.export("VvfpHeathenAgingEventGone", 5, 1, 0, 5), 2)
        self.assertEqual((v.i32(camp, HEALTH), v.i32(camp, CAUSE)), (0, -1), "a body: the event tells its cause")
        self.assertEqual(v.read(camp + PRESENT, 1), b"\x01")
        self.assertEqual(v.u32(DEATHS_STAT), 7)
        self.assertEqual(v.died, [])

    def test_a_disappearance_is_the_events_own_record(self):
        v = Village((EVENTS, BONES_ALL))
        camp = v.villager(1, heathen=True)
        v.villager(9, heathen=True)
        self.assertEqual(v.export("VvfpHeathenAgingEventGone", 5, 1, 1, 5), 1)
        self.assertEqual(v.read(camp + PRESENT, 1), b"\x00", "taken with no body, skeleton row or not")
        self.assertEqual(v.died, [], "the event writes the Disappeared record")
        # Codex on #852: the record stays as it was left (the presence byte cleared) until the event has logged the
        # disappearance -- the replacement is owed, never made into that record at once
        self.assertEqual(v.created, [])
        v.credit(v.record(9), 1)                           # the next look pays it
        self.assertEqual(len(v.created), 1)
        self.assertEqual(v.arrived[-1][1], "Replaced a Heathen lost in an island event")

    def test_never_a_replacement_for_a_former_villager_after_the_last_heathen_or_from_nothing(self):
        for case in ("former", "last", "nothing"):
            with self.subTest(case=case):
                v = Village((EVENTS,))
                r = v.villager(1, heathen=True, parents=case == "former")
                if case != "nothing":
                    v.villager(9, heathen=True)
                if case == "last":
                    v.solve(25)
                self.assertEqual(v.export("VvfpHeathenAgingEventGone", 5, 1, 0, -1), 1)
                self.assertEqual(v.read(r + PRESENT, 1), b"\x00")
                self.assertEqual(v.created, [])

    def test_a_believer_is_never_this_companions(self):
        v = Village((EVENTS,))
        r = v.villager(1, heathen=False)
        self.assertEqual(v.export("VvfpHeathenAgingEventGone", 5, 1, 0, 5), 0)
        self.assertEqual(v.read(r + PRESENT, 1), b"\x01")
        woman = v.villager(2, heathen=True, sex=1)
        self.assertEqual(v.export("VvfpHeathenAgingEventPregnancy", 5, 2, 1, 1, 0), 0, "never with a believer father")
        self.assertEqual(v.i32(woman, PREGNANT), 0)

    def test_a_pregnancy_is_carried_and_born_a_heathen_with_no_aging_row(self):
        v = Village((EVENTS,))
        man = v.villager(1, heathen=True, sex=0, name="Kalo")
        woman = v.villager(2, heathen=True, sex=1, name="Mele")
        v.put32(TWINS, 3)
        self.assertEqual(v.export("VvfpHeathenAgingEventPregnancy", 5, 2, 1, 1, 0), 1)
        self.assertEqual(v.cstring(v.conceived[0][1][3]), "Kalo")
        self.assertEqual(v.u32(TWINS), 3, "never counted")
        at = v.i32(woman, PREGNANT)
        self.assertNotEqual(at, 0)
        v.credit(woman, 42)
        self.assertEqual(v.i32(woman, AGE), 642, "she ages while she carries, as a believer")
        v.credit(man, 41)
        self.assertEqual(v.i32(man, AGE), 600, "nobody else ages")
        v.rand_answers.extend([0, 0, 1])
        v.life_tick()
        self.assertEqual(len(v.created), 1, "born 40 units after the conception")
        baby = v.record(v.created[0][0])
        self.assertEqual(v.read(baby + FACTION, 1), b"\x01")
        self.assertEqual(v.cstring(baby + FATHER_NAME), "Kalo")
        self.assertEqual(v.i32(woman, PREGNANT), 0)
        before = v.i32(woman, AGE)
        v.credit(woman, 5)
        self.assertEqual(v.i32(woman, AGE), before, "born: she stops aging again")

    def test_an_owed_replacement_says_the_real_cause_when_it_is_paid(self):
        """#852 (logs must be correct): a replacement owed while the table was full keeps how the one replaced was
        lost, so its Arrived record says the island event, never "died of old age" -- and an old age's still says so."""
        for how, words in ((0, "Replaced a Heathen lost in an island event"),
                           (None, "Replaced a Heathen who died of old age")):
            with self.subTest(how=how):
                v = Village((TRIBE, EVENTS, BONES_ALL))
                for i in range(150):
                    v.villager(i, heathen=True)
                if how is None:
                    _due_to_die(v, v.record(7))
                    v.life_tick()
                else:
                    self.assertEqual(v.export("VvfpHeathenAgingEventGone", 5, 7, how, 5), 2)
                self.assertEqual(v.created, [], "a full table: owed")
                v.write(v.record(40) + PRESENT, b"\x00")
                v.put32(v.record(8) + AGE, 601)
                v.life_tick()
                self.assertEqual([i for i, _ in v.created], [40])
                self.assertEqual(v.arrived[-1], (40, words))

    def test_a_nursing_baby_is_born_at_once_and_none_after_the_last_heathen(self):
        v = Village((EVENTS,))
        v.villager(1, heathen=True, sex=0)
        woman = v.villager(2, heathen=True, sex=1)
        v.rand_answers.extend([0, 0, 1])
        self.assertEqual(v.export("VvfpHeathenAgingEventPregnancy", 5, 2, -1, 1, 1), 1)
        self.assertEqual(len(v.created), 1)
        self.assertEqual(v.i32(woman, PREGNANT), 0)
        v = Village((EVENTS,))
        v.villager(1, heathen=True, sex=0)
        v.villager(2, heathen=True, sex=1)
        v.solve(25)
        self.assertEqual(v.export("VvfpHeathenAgingEventPregnancy", 5, 2, 1, 1, 0), 0)
        self.assertEqual(v.conceived, [])


if __name__ == "__main__":
    unittest.main()
