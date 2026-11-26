"""New Believers: the Heathens' own graves at the mud hut -- "VVFP Heathen Mausoleum.dll" (workstream W-C of
docs/heathen-tribe-expansion-design.md section 6, with the owner's decisions 11-14 in
docs/heathen-tribe-expansion-decisions.md).

EMULATED on the stock New Believers executable: the companion is started as the start-up chain starts it, then the
game's own code runs over hand-made records: the burial's roster write (0x473F8F..0x473FAE, with the game's own
roster writer 0x464C70), the burial script's carry walk (0x45B650..0x45B66F), the Heathen AI's entry 0x46E9E0, the
believers' chooser's body finder (0x46F141..0x46F14B), the Mausoleum screen's four roster reads, the mausoleum's own
opener (0x43CE24), the lcmap loads (0x423E2B, 0x4246E1), the area-handler dispatchers (click 0x479740, drop 0x4794A0,
hover 0x479780 with the game's own grid lookup), the save 0x4244F0 (whole, its other copies stood in for), the new
village's roster clear (0x42472E) and the load's roster read (0x42583D..0x42584E, with the game's own 0x464EF0).
Stood in for: rand 0x403660 (answers queued), the epitaph text lookups 0x450D40 / 0x4506D0, the walk step 0x4745A0,
the activity stop 0x473440, the action starter 0x465580, the screen 0x43CC00, the lcmap file read 0x4775B0, the game
clock 0x425950 / 0x4036E0, the villager's point 0x466350 and the save file writer 0x403940.  The companion's .dat
lives in an in-memory file system, so what it writes, reads, sets aside and merges is real.
"""
from __future__ import annotations

import collections
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

try:
    from test_companion_installs_all_or_none import (HAVE_EMULATOR, Machine, render, stock_path,
                                                      whole_catalog, with_requirements)
    from story_emulator import RETURN, STACK_TOP, EmulationError
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

DLL = ROOT / "assets" / "heathen_mausoleum" / "VVFP Heathen Mausoleum.dll"
ROW_FLAG = "VVFP Heathen Tribe Evolution.txt"
FORMER_FLAG = "VVFP Heathen Skeletons Former.txt"
ALL_FLAG = "VVFP Heathen Skeletons All.txt"
FORMER_ROW = "vv5_former_villager_heathens_leave_skeletons"
MODES = ("stock", "collection_progression", "immediate_fixed")

MANAGER = 0x554148
RECORDS = MANAGER + 0x48
STRIDE = 0x2F44
SELF, AGE, SEX, NAME, HEAD, BODY = 0x1B88, 0x1B8C, 0x1B90, 0x1B9C, 0x1BB8, 0x1BBC
FATHER_NAME, MOTHER_NAME = 0x1BC0, 0x1BD9
STAMP, HEALTH, CAUSE, SICK, PREGNANT, SKILLS = 0x1C38, 0x1C40, 0x1C44, 0x1C48, 0x1C4C, 0x1C5C
ID, PRESENT, LOOKALIKE, FACTION, ROLE, BEHAVIOUR = 0x1C94, 0x1CD4, 0x1CE1, 0x1CEC, 0x1CFC, 0x1D10
ROSTER = 0x5481A8
ENTRY = 0x5C
BODY_INDEX = 0x547D54
GRID = 0x718EE8
AREAS = 0x77DC80
SAVE_MANAGER = 0x4DACE0
GAME_OBJECT = 0x30000000
HEATHEN_FILE = "Heathen Mausoleum - Save {0}.dat"
HUT = (2200, 1588)                 # a point at the mud hut (x, y)
SITES = {0x473FA9: 5, 0x45B650: 31, 0x46E9E0: 7, 0x46F146: 5, 0x43F4F1: 5, 0x43F735: 5, 0x43FDC0: 5,
         0x43FED6: 5, 0x43CE24: 5, 0x423E2B: 5, 0x4246E1: 5, 0x424569: 5, 0x424733: 5, 0x425849: 5, 0x43F1DF: 5,
         0x46B116: 10}


def _skip() -> str | None:
    if not HAVE_EMULATOR:
        return "unicorn/pefile not installed"
    if not stock_path(5).is_file():
        return "stock executable not present (inputs/)"
    if not DLL.is_file():
        return f"{DLL} missing"
    return None


class Village(Machine):
    def __init__(self, flags: tuple[str, ...] = (ROW_FLAG,), *, exe: bytes | None = None,
                 mutate: tuple[int, int] | None = None):
        image = bytearray(exe if exe is not None else stock_path(5).read_bytes())
        if mutate is not None:
            image[mutate[0] - 0x400000] ^= mutate[1]
        super().__init__(bytes(image), DLL, present=flags)
        self.rand_answers: collections.deque[int] = collections.deque()
        self.rand_calls: list[int] = []
        self.walks: list[tuple[int, int, int, int, int]] = []
        self.started: list[tuple[int, int]] = []
        self.stopped: list[int] = []
        self.opened = 0
        self.clock = 0
        self.files: dict[str, bytes] = {}
        self.locked: set[str] = set()
        self.handles: dict[int, list] = {}
        self.last_error = 0
        self.save_ok = 1
        self.saved: list[int] = []
        self.api_handlers["GetModuleHandleA"] = lambda p: ((0x400000 if p.arg(0) == 0 else 0), 4)
        self.api_handlers["GetTickCount"] = self._tick
        for name, fn in (("CreateFileA", self._create_file), ("ReadFile", self._read_file),
                         ("WriteFile", self._write_file), ("FlushFileBuffers", lambda p: (1, 4)),
                         ("CloseHandle", self._close), ("MoveFileExA", self._move_file),
                         ("DeleteFileA", self._delete_file), ("GetLastError", lambda p: (p.last_error, 0)),
                         ("CreateDirectoryA", lambda p: (1, 8)), ("SHGetSpecialFolderPathA", self._documents)):
            self.api_handlers[name] = fn
        self.stub(0x403660, self._rand)
        self.words = self.alloc(0x1000)
        self.stub(0x450D40, lambda p: (p.arg(0), 4))
        self.stub(0x4506D0, self._text)
        self.stub(0x4745A0, self._walk)
        self.stub(0x473440, self._stop)
        self.stub(0x465580, self._start)
        self.stub(0x43CC00, self._open)
        self.stub(0x4775B0, lambda p: (0, 0))
        self.stub(0x425950, lambda p: (GAME_OBJECT, 0))
        self.stub(0x4036E0, lambda p: (p.clock, 0))
        self.stub(0x466350, self._point)
        self.mu.mem_map(GAME_OBJECT, 0x20000)
        self.put32(GAME_OBJECT + 0x17D7C, 1)
        self.point = HUT
        self.save_manager = self.alloc(0x18000)
        self.put32(SAVE_MANAGER, self.save_manager)
        self.slot(1)
        self.installed = self.export("VvfpStartup", 5, 0)
        self.installed = self.export("VvfpHeathenMausoleumInstalled")

    # ---- the APIs -----------------------------------------------------------------------------------------
    def _tick(self, p):
        self.tick += 977
        return self.tick, 0

    def _documents(self, p):
        p.write(p.arg(1), b"C:\\Docs\0")
        return 1, 16

    def _create_file(self, p):
        name, disposition = p.cstring(p.arg(0)), p.arg(4)
        if name in self.locked:
            self.last_error = 32                                        # ERROR_SHARING_VIOLATION
            return 0xFFFFFFFF, 28
        if disposition == 3 and name not in self.files:                 # OPEN_EXISTING
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
        if dst in self.files and not (p.arg(2) & 1):
            self.last_error = 183
            return 0, 12
        self.files[dst] = self.files.pop(src)
        return 1, 12

    def _delete_file(self, p):
        return int(self.files.pop(p.cstring(p.arg(0)), None) is not None), 4

    # ---- the game's routines stood in for -----------------------------------------------------------------
    def _rand(self, p):
        n = p.arg(0)
        self.rand_calls.append(n)
        value = self.rand_answers.popleft() if self.rand_answers else 0
        return value % n, 0

    def _text(self, p):
        at = self.words + (p.reg("ecx") & 0x3F) * 16
        p.write(at, b"Ep%d\0" % (p.reg("ecx") & 0x3FF))
        return at, 0

    def _walk(self, p):
        self.walks.append((p.reg("ecx"), p.arg(0), p.arg(1), p.arg(2), p.arg(3)))
        return 0, 16

    def _stop(self, p):
        self.stopped.append(p.reg("ecx"))
        return 0, 0

    def _start(self, p):
        record = p.reg("ecx")
        p.put32(record + BEHAVIOUR, p.arg(0))
        self.started.append((record, p.arg(0), p.u32(BODY_INDEX)))
        return 0, 8

    def _open(self, p):
        self.opened += 1
        return 0, 0

    def _point(self, p):
        out = p.arg(0)
        p.put32(out, self.point[0])
        p.put32(out + 4, self.point[1])
        return out, 4

    # ---- records ------------------------------------------------------------------------------------------
    def record(self, index: int) -> int:
        return RECORDS + index * STRIDE

    def villager(self, index: int, *, heathen: bool, age: int = 600, health: int = 90, role: int = 0,
                 name: str | None = None, parents: bool = False, cause: int = -1) -> int:
        r = self.record(index)
        self.write(r, bytes(STRIDE))
        self.put32(r + SELF, r)
        self.write(r + NAME, (name or f"V{index}").encode() + b"\0")
        self.put32(r + AGE, age)
        self.put32(r + HEALTH, health & 0xFFFFFFFF)
        self.put32(r + CAUSE, cause & 0xFFFFFFFF)
        self.put32(r + HEAD, 4)
        self.put32(r + BODY, 7)
        self.put32(r + ID, 1000 + index)
        self.write(r + PRESENT, b"\x01")
        self.write(r + FACTION, b"\x01" if heathen else b"\x00")
        self.put32(r + ROLE, role)
        if parents:
            self.write(r + FATHER_NAME, b"Dad\0")
            self.write(r + MOTHER_NAME, b"Mum\0")
        return r

    def dead(self, index: int, *, heathen: bool, lain: int = 0, **kw) -> int:
        """A body lying unburied for `lain` age units (the game clock is in seconds, one unit a minute here)."""
        r = self.villager(index, heathen=heathen, health=0, cause=kw.pop("cause", 2), **kw)
        self.clock = max(self.clock, 1_000_000)
        self.put32(r + STAMP, self.clock - lain * 60)
        return r

    def slot(self, slot: int) -> None:
        self.put32(self.save_manager + 0x17D80, slot)

    # ---- the companion ------------------------------------------------------------------------------------
    def count(self) -> int:
        return self.export("VvfpHeathenMausoleumCount")

    def entry(self, place: int) -> int:
        return self.export("VvfpHeathenMausoleumEntry", place)

    def table(self) -> int:
        return self.export("VvfpHeathenMausoleumTable")

    def names(self) -> list[str]:
        return [self.cstring(self.entry(i)) for i in range(self.count())]

    def stock_names(self) -> list[str]:
        out = []
        for i in range(500):
            e = ROSTER + i * ENTRY
            if self.u32(e + 0x1C) == 0:
                break
            out.append(self.cstring(e))
        return out

    def file(self, slot: int = 1) -> bytes | None:
        for name, data in self.files.items():
            if name.endswith("\\" + HEATHEN_FILE.format(slot)):
                return data
        return None

    def file_name(self, slot: int = 1) -> str:
        return ("C:\\Docs\\LDW\\Game\\Virtual Villagers Fun Patcher\\Save {0}\\Data\\Heathen Mausoleum\\"
                + HEATHEN_FILE).format(slot)

    # ---- the game -----------------------------------------------------------------------------------------
    def _regs(self, **regs) -> None:
        self.set_reg("esp", STACK_TOP - 0x4000)
        for name, value in regs.items():
            self.set_reg(name, value)

    def bury(self, body: int, burier: int) -> int:
        """op 0x1D's end: the record freed, the burier's id and the body pushed, the roster write (0x473FA9)."""
        owner = self.alloc(0x2000)
        self.put32(owner + 0x1B80, burier)
        self._regs(esi=body, ebx=owner)
        self.run(0x473F8F, 0x473FAE)
        return self.reg("eax") & 0xFF

    def carry(self, burier: int, body_index: int, roll: int = 7) -> tuple[int, int]:
        self.put32(BODY_INDEX, body_index)
        self.rand_answers.append(roll)
        self._regs(esi=burier)
        self.run(0x45B650, 0x45B66F)
        _, x, y, _, _ = self.walks[-1]
        return x, y

    def ai(self, record: int) -> str:
        """The Heathen AI entry: 'buried' (it returned having started a burial) or 'stock' (the stock AI went on:
        its next instruction 0x46E9E7 is reached, and the run ends there)."""
        self.stock_ai = False

        def stock(p):
            p.stock_ai = True
            p.put32(p.reg("esp"), RETURN)          # (abandon the stock AI's frame: the run is over)
            return 0, 0
        self.stub(0x46E9E7, stock)
        self.call(0x46E9E0, ecx=record)
        return "stock" if self.stock_ai else "buried"

    def finder(self) -> int:
        self._regs()
        self.run(0x46F141, 0x46F14B)
        return struct.unpack("<i", struct.pack("<I", self.reg("eax")))[0]

    def lcmap(self, site: int = 0x423E2B) -> None:
        self._regs(ecx=GRID)
        self.put32(self.reg("esp"), RETURN)
        self.run(site, site + 5)

    def cell(self, x: int, y: int) -> int:
        return self.u32(GRID + ((y // 8) * 320 + x // 8) * 4)

    def screen_count(self) -> int:
        self._regs(esi=self.alloc(0x40))
        self.run(0x43F4F1, 0x43F4FB)
        return self.reg("eax")

    def screen_rows(self, place: int) -> list[int]:
        """Each of the three entry reads (row draw, click, hover) for `place`: the entry it got."""
        got = []
        for start, end in ((0x43F734, 0x43F73F), (0x43FDBF, 0x43FDCA), (0x43FED5, 0x43FEE0)):
            self._regs(eax=place)
            self.run(start, end)
            got.append(self.reg("eax"))
        return got

    def click(self, x: int, y: int) -> int:
        return self.call(0x479740, [x, y], ecx=0x77DECC) & 0xFF

    def drop(self, villager: int) -> int:
        return self.call(0x4794A0, [villager, 1], ecx=0x77DECC) & 0xFF

    def hover(self, villager: int) -> int:
        return self.call(0x479780, [villager], ecx=0x77DECC) & 0xFF

    def stock_open(self) -> None:
        self._regs()
        self.put32(self.reg("esp"), RETURN)
        self.run(0x43CE24, 0x43CE29)

    def save(self, slot: int, *, ok: int = 1) -> int:
        """The game's save 0x4244F0(slot), whole; its other copies and the file writer stood in for."""
        for at, pop in ((0x412EC0, 4), (0x413B80, 4), (0x41EB30, 4), (0x41EC40, 4), (0x41ECE0, 4), (0x43AD10, 8),
                        (0x4235B0, 4), (0x44E590, 4), (0x46F9B0, 4)):
            self.stub(at, lambda p, pop=pop: (0, pop))
        self.stub(0x403940, lambda p: (self.saved.append(p.arg(2)) or ok, 12))
        return self.call(0x4244F0, [slot], ecx=self.save_manager) & 0xFF

    def new_village(self) -> None:
        self._regs()
        self.run(0x42472E, 0x424738)

    def load(self, slot: int) -> int:
        """The load's roster read (0x42583D..0x42584E): the game's own 0x464EF0 from the save buffer, then the
        slot's Heathen graves."""
        self.slot(slot)
        self._regs(ebx=self.save_manager)
        self.run(0x42583D, 0x42584E)
        return self.reg("eax") & 0xFF


def _site_bytes(exe: bytes, va: int, n: int) -> bytes:
    return exe[va - 0x400000: va - 0x400000 + n]


@unittest.skipIf(_skip(), _skip() or "")
class Installs(unittest.TestCase):
    def test_installs_with_each_shipping_row_and_not_without(self):
        self.assertEqual(Village(()).installed, 0)
        for flag in (ROW_FLAG, FORMER_FLAG, ALL_FLAG):
            with self.subTest(flag=flag):
                self.assertEqual(Village((flag,)).installed, 1)

    def test_one_wrong_stock_byte_at_any_site_installs_nothing(self):
        for va, n in SITES.items():
            for offset in (0, n - 1):
                with self.subTest(site=hex(va), offset=offset):
                    v = Village(mutate=(va + offset, 0x01))
                    self.assertEqual(v.installed, 0)
                    self.assertEqual(v.image_writes, [], "nothing written")

    def test_the_sites_are_stock_in_every_mode_and_with_the_whole_catalog(self):
        rows = with_requirements(5, [FORMER_ROW])
        renders = [(mode, render(5, rows, mode)) for mode in MODES]
        renders.append(("catalog", render(5, whole_catalog(5), "collection_progression")))
        stock = stock_path(5).read_bytes()
        for what, exe in renders:
            with self.subTest(render=what):
                for va, n in SITES.items():
                    self.assertEqual(_site_bytes(exe, va, n), _site_bytes(stock, va, n), hex(va))
                v = Village((FORMER_FLAG,), exe=exe)
                self.assertEqual(v.installed, 1)
                v.villager(0, heathen=False, name="Bel")
                v.dead(1, heathen=True, name="Hea")
                v.bury(v.record(1), v.record(0))
                self.assertEqual(v.names(), ["Hea"])

    def test_the_256_build_buries_and_finds_past_record_150(self):
        """The whole catalog carries 256 Villagers (Experimental): the table at 0x800000, 256 records."""
        exe = render(5, whole_catalog(5), "collection_progression")
        v = Village((ROW_FLAG,), exe=exe)
        self.assertEqual(v.installed, 1)
        base = 0x800000 + 0x48
        v.record = lambda index: base + index * STRIDE          # type: ignore[method-assign]
        v.villager(0, heathen=True, name="Able")
        v.dead(200, heathen=True, name="Far", lain=10)
        self.assertEqual(v.finder(), -1, "the Heathens' own, past record 150")
        v.dead(200, heathen=True, name="Far", lain=130)
        self.assertEqual(v.finder(), 200)
        for _ in range(40):
            if v.ai(v.record(0)) == "buried":
                break
        self.assertEqual(v.started[-1], (v.record(0), 0x30, 200))
        burier = v.villager(1, heathen=False)
        v.bury(v.record(200), burier)
        self.assertEqual(v.names(), ["Far"])


@unittest.skipIf(_skip(), _skip() or "")
class Burial(unittest.TestCase):
    def test_burial_routes_by_the_faction_at_death(self):
        v = Village()
        burier = v.villager(0, heathen=False, name="Burier")
        v.dead(1, heathen=True, name="CampHea", age=1200)
        v.dead(2, heathen=False, name="Believer", age=900)
        v.dead(3, heathen=True, name="FormerHea", parents=True, age=1100)     # a former villager, died a Heathen
        v.dead(4, heathen=False, name="Converted", parents=True, age=1000)    # a Heathen who converted, then died
        for i in (1, 2, 3, 4):
            self.assertEqual(v.bury(v.record(i), burier), 1, i)
        self.assertEqual(v.names(), ["CampHea", "FormerHea"])
        self.assertEqual(v.stock_names(), ["Believer", "Converted"])
        e = v.entry(0)
        self.assertEqual((v.u32(e + 0x1C), v.u32(e + 0x20), v.u32(e + 0x24), v.u32(e + 0x34)), (1200, 4, 7, 2),
                         "the game's own writer filled the entry: age, head, body, cause")
        self.assertTrue(v.cstring(e + 0x38).startswith("Ep"), "...and its epitaph")
        self.assertEqual(v.u32(v.table() + 0xB3B0), 1000, "the burier's id, as the stock roster keeps it")
        for i in (1, 2, 3, 4):
            self.assertEqual(v.read(v.record(i) + PRESENT, 1), b"\0")
        self.assertEqual(v.export("VvfpHeathenMausoleumIsHeathenGrave", e), 1)
        self.assertEqual(v.export("VvfpHeathenMausoleumIsHeathenGrave", ROSTER), 0)
        self.assertEqual(v.export("VvfpHeathenMausoleumIsHeathenGrave", e + 4), 0)

    def test_the_everyday_honoring_counts_the_heathens_graves_too(self):
        """0x46B116..0x46B120: the "Honoring the dead" chooser's grave count is the believers' and the Heathens'."""
        def honoring_count(v: Village) -> int:
            v._regs()
            v.run(0x46B116, 0x46B120)
            return v.reg("eax")
        v = Village()
        self.assertEqual(honoring_count(v), 0)
        burier = v.villager(0, heathen=False)
        v.dead(1, heathen=True, name="H1")
        v.bury(v.record(1), burier)
        self.assertEqual(honoring_count(v), 1, "a village whose only grave is a Heathen's still honors its dead")
        v.dead(2, heathen=False, name="B1")
        v.bury(v.record(2), burier)
        v.dead(3, heathen=True, name="H2")
        v.bury(v.record(3), burier)
        self.assertEqual(honoring_count(v), 3)
        self.assertEqual(honoring_count(Village(())), 0, "without the companion: the game's own count")

    def test_a_full_mud_hut_memorial_writes_no_grave(self):
        v = Village()
        table = v.table()
        for i in range(500):
            v.write(table + i * ENTRY, b"Old\0")
            v.put32(table + i * ENTRY + 0x1C, 100)
        burier = v.villager(0, heathen=False)
        v.dead(1, heathen=True, name="Late")
        self.assertEqual(v.bury(v.record(1), burier), 0, "the writer's own answer: full")
        self.assertEqual(v.count(), 500)
        self.assertEqual(v.stock_names(), [], "never into the believers' roster")

    def test_without_the_companion_every_grave_is_the_stock_rosters(self):
        v = Village(())
        burier = v.villager(0, heathen=False)
        v.dead(1, heathen=True, name="Hea")
        v.bury(v.record(1), burier)
        self.assertEqual(v.stock_names(), ["Hea"])

    def test_a_heathens_body_is_carried_to_the_mud_hut(self):
        v = Village()
        burier = v.villager(0, heathen=False)
        v.dead(1, heathen=True)
        v.dead(2, heathen=False)
        self.assertEqual(v.carry(burier, 1, roll=7), (2176 + 35, 1588))
        self.assertEqual(v.carry(burier, 2, roll=7), (0x7D + 7, 0x6BD), "a believer's: the mausoleum door")
        self.assertEqual(v.rand_calls, [20, 20], "the stock script's rand(20), once a walk")
        self.assertEqual([w[0] for w in v.walks], [burier, burier])
        self.assertEqual([w[3:] for w in v.walks], [(100, 0), (100, 0)])

    def test_a_reused_record_slot_keeps_each_grave_where_it_belongs(self):
        v = Village()
        burier = v.villager(0, heathen=False)
        v.dead(5, heathen=True, name="FirstHea", age=1300)
        v.bury(v.record(5), burier)
        v.dead(5, heathen=False, name="NextBel", age=700)          # the record reused by a believer
        v.bury(v.record(5), burier)
        v.dead(5, heathen=True, name="ThirdHea", age=500)          # ...and by a Heathen again
        v.bury(v.record(5), burier)
        self.assertEqual(v.names(), ["FirstHea", "ThirdHea"])
        self.assertEqual(v.stock_names(), ["NextBel"])
        self.assertEqual([v.u32(v.entry(i) + 0x1C) for i in range(2)], [1300, 500])


@unittest.skipIf(_skip(), _skip() or "")
class Buriers(unittest.TestCase):
    def ask(self, v: Village, record: int, tries: int = 40) -> str:
        for _ in range(tries):
            if v.ai(record) == "buried":
                return "buried"
        return "stock"

    def test_an_able_heathen_buries_a_heathens_body(self):
        v = Village()
        a = v.villager(0, heathen=True, name="Able", age=600)
        v.dead(3, heathen=True)
        self.assertEqual(self.ask(v, a), "buried")
        self.assertEqual(v.started[-1], (a, 0x30, 3), "the game's own Burying the dead, the body in 0x547D54")
        self.assertEqual(v.stopped[-1], a, "the activity stopped first, as the believers' chooser does")

    def test_heathens_take_it_about_half_the_times_they_are_asked(self):
        v = Village()
        a = v.villager(0, heathen=True)
        v.dead(3, heathen=True)
        answers = []
        for _ in range(200):
            answers.append(v.ai(a))
            v.put32(a + BEHAVIOUR, 0)            # asked anew each time: never still burying
        took = answers.count("buried")
        self.assertTrue(60 <= took <= 140, took)

    def test_who_never_buries(self):
        cases = {
            "a believer's body": dict(body_heathen=False),
            "a child": dict(age=200),
            "sick": dict(sick=True),
            "expecting": dict(pregnant=True),
            "the Chief": dict(role=13),
            "the Doctor": dict(role=12),
            "the Mommy": dict(role=17),
            "no body": dict(no_body=True),
        }
        for what, case in cases.items():
            with self.subTest(what):
                v = Village()
                a = v.villager(0, heathen=True, age=case.get("age", 600), role=case.get("role", 0))
                if case.get("sick"):
                    v.write(a + SICK, b"\x01")
                if case.get("pregnant"):
                    v.put32(a + PREGNANT, 50)
                if not case.get("no_body"):
                    v.dead(3, heathen=case.get("body_heathen", True))
                self.assertEqual(self.ask(v, a), "stock")
                self.assertEqual(v.started, [])

    def test_a_body_one_heathen_is_burying_is_left_to_it(self):
        v = Village()
        a = v.villager(0, heathen=True, name="A")
        b = v.villager(1, heathen=True, name="B")
        v.dead(3, heathen=True)
        self.assertEqual(self.ask(v, a), "buried")
        v.carry(a, 3)                                   # its script queued: the carry walk claims the body
        self.assertEqual(self.ask(v, b), "stock", "nobody else goes for it")
        v.put32(a + BEHAVIOUR, 0x10)                    # A gave up (another action)
        self.assertEqual(self.ask(v, b), "buried")

    def test_believers_wait_for_the_heathens_then_fall_back(self):
        v = Village()
        v.villager(0, heathen=True)                     # an able Heathen lives
        v.dead(3, heathen=True, lain=10)
        self.assertEqual(v.finder(), -1, "a fresh Heathen body is the Heathens' to bury")
        v.dead(3, heathen=True, lain=120)
        self.assertEqual(v.finder(), 3, "lain 120 units: the believers' fallback")
        v.dead(3, heathen=True, lain=10)
        v.villager(0, heathen=True, role=13)            # only a puzzle Heathen: nobody able
        self.assertEqual(v.finder(), 3)
        v.villager(0, heathen=False)
        self.assertEqual(v.finder(), 3, "no Heathen at all")

    def test_the_believers_finder_keeps_the_stock_rule_for_believers(self):
        v = Village()
        v.villager(0, heathen=True)
        v.dead(2, heathen=True)                         # deferred to the Heathens
        v.dead(5, heathen=False)
        self.assertEqual(v.finder(), 5)
        v.dead(1, heathen=False)
        self.assertEqual(v.finder(), 1, "the first body, as 0x470940")
        v.write(v.record(1) + LOOKALIKE, b"\x01")
        self.assertEqual(v.finder(), 5, "a look-alike is no body (0x466170)")

    def test_a_body_being_buried_is_not_taken_by_the_fallback(self):
        v = Village()
        a = v.villager(0, heathen=True)
        v.dead(3, heathen=True, lain=200)
        self.assertEqual(self.ask(v, a), "buried")
        v.carry(a, 3)
        self.assertEqual(v.finder(), -1)


@unittest.skipIf(_skip(), _skip() or "")
class Screen(unittest.TestCase):
    def village_with_graves(self, *names: str) -> Village:
        v = Village()
        burier = v.villager(0, heathen=False)
        for i, name in enumerate(names):
            v.dead(10 + i, heathen=True, name=name)
            v.bury(v.record(10 + i), burier)
        v.dead(20, heathen=False, name="Bel")
        v.bury(v.record(20), burier)
        return v

    def test_the_hut_is_registered_and_stamped_after_each_lcmap_load(self):
        for site in (0x423E2B, 0x4246E1):
            with self.subTest(site=hex(site)):
                v = Village()
                v.put32(GRID + ((1500 // 8) * 320 + 2160 // 8) * 4, 0x2C << 15 | 1)   # another hotspot: kept
                v.put32(GRID + ((1500 // 8) * 320 + 2200 // 8) * 4, 1)                 # a blocked cell
                v.lcmap(site)
                handler, highlight, permission = struct.unpack("<3I", v.read(AREAS + 0x0B * 12, 12))
                self.assertTrue(v.dll_base <= handler < v.dll_base + v.dll_size)
                self.assertEqual((highlight, permission), (6, 1))
                self.assertEqual((v.cell(2200, 1500) >> 15) & 0x3FF, 0x0B)
                self.assertEqual(v.cell(2200, 1500) & 1, 1, "the cell's other bits kept")
                self.assertEqual((v.cell(2160, 1500) >> 15) & 0x3FF, 0x2C)
                for x, y in ((2152, 1464), (2287, 1599), (2200, 1588)):
                    self.assertEqual((v.cell(x, y) >> 15) & 0x3FF, 0x0B, (x, y))
                for x, y in ((2144, 1500), (2288, 1500), (2200, 1456), (2200, 1600)):
                    self.assertEqual(v.cell(x, y), 0, (x, y))

    def test_no_stamp_without_the_companion(self):
        v = Village(())
        v.lcmap()
        self.assertEqual(v.cell(2200, 1500), 0)
        self.assertEqual(v.u32(AREAS + 0x0B * 12), 0)

    def test_a_click_on_the_hut_opens_the_screen_on_the_heathens_graves(self):
        v = self.village_with_graves("H1", "H2", "H3")
        v.lcmap()
        self.assertEqual(v.screen_count(), 1, "before: the believers' roster")
        self.assertEqual(v.click(*HUT), 1)
        self.assertEqual(v.opened, 1)
        self.assertEqual(v.screen_count(), 3)
        for place in range(3):
            self.assertEqual(v.screen_rows(place), [v.entry(place)] * 3, place)
        self.assertEqual(v.screen_rows(3), [0, 0, 0], "past the last: none, as 0x464E70")
        self.assertEqual(v.stock_names(), ["Bel"], "the believers' roster unchanged")
        v.stock_open()
        self.assertEqual(v.opened, 2)
        self.assertEqual(v.screen_count(), 1, "the mausoleum's own opener: the believers again")
        self.assertEqual(v.screen_rows(0), [ROSTER] * 3)

    def test_a_drop_on_the_hut_opens_it_too_and_a_hover_keeps_the_hover_lines(self):
        v = self.village_with_graves("H1")
        v.lcmap()
        child = v.villager(1, heathen=False, age=100)
        adult = v.villager(2, heathen=False, age=600)
        v.put32(adult + PREGNANT, 30)
        for who in (child, adult):
            v.opened = 0
            self.assertEqual(v.hover(who), 0, "not taken: the point-hover routine runs (hovel hover lines)")
            self.assertEqual(v.opened, 0)
            self.assertEqual(v.drop(who), 1)
            self.assertEqual(v.opened, 1)
            self.assertEqual(v.screen_count(), 1)

    def test_the_screen_title_is_the_shrine_to_the_ancestors_for_the_heathens(self):
        """The scene's title widget (made at 0x43F1DF from string 0x4D) says "Shrine to the Ancestors" while the
        Heathens' graves are shown and the game's own title otherwise; made before or after the first opening."""
        for first in ("hut", "mausoleum"):
            with self.subTest(first_opened_from=first):
                v = self.village_with_graves("H1")
                v.lcmap()
                titles: list[tuple[int, str]] = []
                widget = v.alloc(0x40)
                stock_title = v.alloc(0x20)
                v.write(stock_title, b"Mausoleum\0")
                v.stub(0x40D8D0, lambda p: (titles.append((p.reg("ecx"), p.cstring(p.arg(0)))) or 0, 4))
                v.stub(0x40DD90, lambda p: (p.reg("ecx"), 0x1C))

                def make_scene():
                    v._regs(ecx=widget)
                    esp = v.reg("esp")
                    for k, value in enumerate((0x6000, 0x1F4, 4, stock_title, 1, 0, 0x3F800000)):
                        v.put32(esp + 4 * k, value)
                    v.run(0x43F1DF, 0x43F1E4)
                    self.assertEqual(v.reg("eax"), widget)
                if first == "hut":
                    self.assertEqual(v.click(*HUT), 1)
                    make_scene()                      # the scene is made at its first opening
                    self.assertEqual(titles[-1], (widget, "Shrine to the Ancestors"))
                    v.stock_open()
                    self.assertEqual(titles[-1], (widget, "Mausoleum"))
                else:
                    v.stock_open()
                    make_scene()
                    self.assertEqual(titles[-1], (widget, "Mausoleum"))
                    self.assertEqual(v.click(*HUT), 1)
                    self.assertEqual(titles[-1], (widget, "Shrine to the Ancestors"))
                    v.stock_open()
                    self.assertEqual(titles[-1], (widget, "Mausoleum"))

    def test_an_empty_mud_hut_memorial_does_not_open(self):
        v = Village()
        v.lcmap()
        self.assertEqual(v.click(*HUT), 0)
        self.assertEqual(v.opened, 0)

    def test_a_click_elsewhere_is_not_the_huts(self):
        v = self.village_with_graves("H1")
        v.lcmap()
        self.assertEqual(v.click(2100, 1588), 0)
        self.assertEqual(v.opened, 0)


@unittest.skipIf(_skip(), _skip() or "")
class SaveAndLoad(unittest.TestCase):
    def two_graves(self) -> Village:
        v = Village()
        burier = v.villager(0, heathen=False)
        for i, name in ((1, "Alpha"), (2, "Beta")):
            v.dead(i, heathen=True, name=name, age=1000 + i)
            v.bury(v.record(i), burier)
        return v

    def test_written_only_when_the_game_saves_the_slot(self):
        v = self.two_graves()
        self.assertIsNone(v.file(1), "no file before a save")
        self.assertEqual(v.save(0), 1)                          # the meta, slot 0
        self.assertEqual(v.save(21), 1)                         # the backup generation, slot + 20
        self.assertIsNone(v.file(1))
        self.assertEqual(v.save(1, ok=0), 0)                    # the game's write failed
        self.assertIsNone(v.file(1))
        self.assertEqual(v.save(1), 1)
        data = v.file(1)
        self.assertEqual(struct.unpack("<5I", data[:20]), (0x314D4856, 1, 5, 2, 1))
        self.assertEqual(len(data), 20 + 2 * ENTRY)
        self.assertEqual(data[20:20 + 2 * ENTRY], v.read(v.table(), 2 * ENTRY))
        self.assertEqual(v.saved, [0, 21, 1, 1], "the game's own writes all went on")

    def test_save_and_load_round_trip_and_a_quit_without_saving(self):
        v = self.two_graves()
        v.save(1)
        kept = v.read(v.table(), 2 * ENTRY)
        burier = v.villager(0, heathen=False)
        v.dead(3, heathen=True, name="Unsaved")
        v.bury(v.record(3), burier)
        self.assertEqual(v.names(), ["Alpha", "Beta", "Unsaved"])
        self.assertEqual(v.load(1), 1)                          # quit without saving, then load
        self.assertEqual(v.names(), ["Alpha", "Beta"])
        self.assertEqual(v.read(v.table(), 2 * ENTRY), kept)
        self.assertEqual(v.read(v.table() + 2 * ENTRY, ENTRY), bytes(ENTRY))

    def test_a_change_tribe_switches_files_and_a_new_village_starts_empty(self):
        v = self.two_graves()
        v.save(1)
        v.slot(2)
        v.new_village()
        self.assertEqual(v.count(), 0)
        burier = v.villager(0, heathen=False)
        v.dead(1, heathen=True, name="Second")
        v.bury(v.record(1), burier)
        v.save(2)
        v.load(1)
        self.assertEqual(v.names(), ["Alpha", "Beta"])
        v.load(2)
        self.assertEqual(v.names(), ["Second"])
        v.load(3)
        self.assertEqual(v.names(), [], "a slot with no file: no Heathen graves")

    def test_a_new_village_overwrites_the_slots_old_graves_at_its_first_save(self):
        v = self.two_graves()
        v.save(1)
        v.new_village()
        v.save(1)
        self.assertEqual(struct.unpack("<5I", v.file(1)[:20])[3], 0)

    def test_an_invalid_file_is_set_aside_never_fed_to_the_game(self):
        bad_entries = {
            "age 0": lambda e: e[:0x1C] + b"\0\0\0\0" + e[0x20:],
            "profession 6": lambda e: e[:0x28] + struct.pack("<i", 6) + e[0x2C:],
            "cause 5": lambda e: e[:0x34] + struct.pack("<i", 5) + e[0x38:],
            "a control byte in the name": lambda e: b"A\x07" + e[2:],
            "a name with no end": lambda e: b"N" * 0x19 + e[0x19:],
        }
        for what, spoil in bad_entries.items():
            with self.subTest(what):
                v = self.two_graves()
                v.save(1)
                name = v.file_name(1)
                good = v.files[name]
                v.files[name] = good[:20] + spoil(good[20:20 + ENTRY]) + good[20 + ENTRY:]
                v.load(1)
                self.assertEqual(v.count(), 0)
                self.assertNotIn(name, v.files)
                self.assertTrue(any(".unreadable-" in n for n in v.files), "kept aside")
        for what, data in (("short", lambda g: g[:-1]), ("another slot", lambda g: g[:16] + b"\2\0\0\0" + g[20:]),
                           ("another version", lambda g: g[:4] + b"\2\0\0\0" + g[8:])):
            with self.subTest(what):
                v = self.two_graves()
                v.save(1)
                name = v.file_name(1)
                v.files[name] = data(v.files[name])
                v.load(1)
                self.assertEqual(v.count(), 0)
                self.assertNotIn(name, v.files)

    def test_a_locked_file_is_never_replaced_and_is_merged_once_it_opens(self):
        v = self.two_graves()
        v.save(1)
        name = v.file_name(1)
        v.locked.add(name)
        v.load(1)
        self.assertEqual(v.count(), 0)
        burier = v.villager(0, heathen=False)
        v.dead(4, heathen=True, name="Gamma")
        v.bury(v.record(4), burier)
        v.save(1)                                               # still locked: not written
        v.locked.clear()
        v.tick += 5000                                          # past the retry wait
        v.save(1)
        self.assertEqual(v.names(), ["Alpha", "Beta", "Gamma"])
        self.assertEqual(struct.unpack("<5I", v.files[name][:20])[3], 3)
        v.load(1)
        self.assertEqual(v.names(), ["Alpha", "Beta", "Gamma"])

    def test_start_over_forgets_the_heathen_graves(self):
        v = self.two_graves()
        v.save(1)
        v.export("VvfpHeathenMausoleumVillageReset", 5, 2)     # another slot: left alone
        self.assertEqual(v.count(), 2)
        v.export("VvfpHeathenMausoleumVillageReset", 4, 1)     # another game
        self.assertEqual(v.count(), 2)
        v.export("VvfpHeathenMausoleumVillageReset", 5, 1)
        self.assertEqual(v.count(), 0)
        del v.files[v.file_name(1)]                             # Save Reset deletes the slot's folder
        v.save(1)
        self.assertEqual(struct.unpack("<5I", v.file(1)[:20])[3], 0, "nothing written back")


@unittest.skipIf(_skip(), _skip() or "")
class Revive(unittest.TestCase):
    def test_the_revive_interface_lists_reads_and_removes_a_grave(self):
        v = Village()
        for i, name in ((1, "One"), (2, "Two"), (3, "Three")):
            burier = v.villager(10 + i, heathen=False)
            v.dead(i, heathen=True, name=name)
            v.bury(v.record(i), burier)
        self.assertEqual(v.count(), 3)
        self.assertEqual(v.entry(0), v.table())
        self.assertEqual(v.entry(3), 0)
        self.assertEqual(v.entry(-1), 0)
        self.assertEqual(v.export("VvfpHeathenMausoleumRemove", 1), 1)
        self.assertEqual(v.names(), ["One", "Three"])
        self.assertEqual(v.u32(v.table() + 0xB3B0 + 4), 1013, "the burier ids moved with their graves")
        self.assertEqual(v.read(v.table() + 2 * ENTRY, ENTRY), bytes(ENTRY))
        self.assertEqual(v.export("VvfpHeathenMausoleumRemove", 2), 0)
        v.save(1)
        v.load(1)
        self.assertEqual(v.names(), ["One", "Three"], "the removal reaches the file at the save")

    def test_not_installed_answers_nothing(self):
        v = Village(())
        self.assertEqual((v.count(), v.table(), v.entry(0), v.export("VvfpHeathenMausoleumRemove", 0)),
                         (0, 0, 0, 0))


if __name__ == "__main__":
    unittest.main()
