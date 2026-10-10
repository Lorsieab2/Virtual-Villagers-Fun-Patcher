"""Cause of Death (all five games): the Deaths and Unaccounted Villagers logs,
and the cause and epitaph on A New Home's and The Lost Children's graves.

The owner, in turn: "for the games that don't write a cause of death like
VV1-VV2, can you add them please?" (in the game, the way VV3-VV5 show it);
"mention it for all 5 games in the logs, age of death too" (in the game's own
age units); "can you also put the epitaphs for VV1-VV2 too?" (pregenerated and
editable, as the later games' are); one Death record per death that leaves a
skeleton, written when it is final, with the grave's skill line and epitaph;
"Disappeared" and "Epitaph changed" records; and "No villager gets
unaccounted for!".

Everything here RUNS: the executable the patcher renders (the row alone, and
every public patch of the game, in all three population modes) and the TEST
build of "VVFP Cause of Death.dll" are mapped into one emulated process
(tests/story_emulator.py); the DLL's installer writes its detours into that
executable, and each test runs the game's OWN instructions through a site --
a death, the burial and its Roster of the Dead write, an unburied body's
removal, the grave popup's Draw and Done, an island event's removal, a
villager creator -- with only leaf routines (rand, the string table, sprintf,
the text draw, the widget calls) scripted.  "VVFP Parentage Export.dll"'s
WriteVillageRecord is a recording stand-in: what the log is given is checked
here, the log files by native/parentage_export/death_log_harness.c and the
companion's own files (the graves file, the roster and its reconciliation)
by native/vvfp_cause_of_death/cause_files_harness.c
(tests/test_deaths_log_and_graves_file.py).
"""
from __future__ import annotations

import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from story_emulator import Process  # noqa: E402

TEST_DLL = ROOT / "tests" / "test_dlls" / "VVFP Cause of Death.test.dll"
SHIPPED_DLL = ROOT / "assets" / "cause_of_death" / "VVFP Cause of Death.dll"
TEST_BUILD_ABSENT = "test builds are not in the release source archive (tests/test_dlls)"
NAMES = {"vv1": "A New Home", "vv2": "The Lost Children", "vv3": "The Secret City",
         "vv4": "The Tree of Life", "vv5": "New Believers"}
STOCK = {g: ROOT / "research" / "stock-executables" / f"Virtual Villagers - {n}.exe"
         for g, n in NAMES.items()}
STOCK_ABSENT = "stock executables are not in the release source archive"
MODES = ("stock", "collection_progression", "immediate_fixed")
STACK = 0x0FF00000 - 0x2000

FAKE_PARENTAGE = 0x0C100000
WRITE_RECORD = 0x0C200000
SLOT_FN = 0x0C200100
DEATH, DISAPPEARED, EPITAPH, UNACCOUNTED = 2, 3, 4, 5
NO_GRAVE = "no grave (never buried: the game removed the body)"
STAT_NAMES = ("deaths", "unhooked", "burials", "graves_set", "draws", "logged", "published",
              "departed", "arrived", "unaccounted", "armed", "backfilled", "arrivals", "arrivals_backfilled",
              "births_backfilled", "left_tribe", "lost")
ARRIVED = 6


def manifest(game: str) -> dict:
    return json.loads((ROOT / "data" / f"{game}_cause_of_death_feature.json").read_text(encoding="utf-8"))


_RENDERS: dict = {}


def rendered(game: str, mode: str, everything: bool) -> bytes:
    key = (game, mode, everything)
    if key not in _RENDERS:
        import vv_fun_patcher as vfp
        build = next(b for b in vfp.load_builds() if b.id == game)
        if everything:
            # The ordinary build: 256 Villagers (Experimental) builds another
            # layout and has its own tests (LaterGames256 below).
            rows = [p.id for p in vfp.load_public_fun_patches()
                    if p.game_id == game and p.id not in vfp.EXPERIMENTAL_FUN_PATCH_IDS]
        else:
            rows = [f"{game}_cause_of_death"]
        data, _ = vfp.render_patched_bytes(STOCK[game], build, mode, rows)
        _RENDERS[key] = bytes(data)
    return _RENDERS[key]


def lines(text: str) -> dict:
    """'  Label: value' lines -> {label: value}."""
    out = {}
    for line in (text or "").splitlines():
        if ":" in line:
            label, value = line.strip().split(":", 1)
            out[label] = value.strip()
    return out


class Game:
    """One emulated game process with the test DLL loaded."""

    def __init__(self, game: str, exe: bytes, slot: int = 0):
        self.game = game
        self.no = int(game[-1])
        self.p = p = Process(exe, TEST_DLL)
        self.logged: list[dict] = []
        self.slot = slot
        self.files: dict[str, bytearray] = {}
        self.dirs: set[str] = set()
        self.handles: dict[int, list] = {}
        self.last_error = 0
        p.mu.mem_map(FAKE_PARENTAGE, 0x1000)
        p.mu.mem_map(WRITE_RECORD, 0x1000)
        p.api_handlers["LoadLibraryA"] = self._load_library
        p.api_handlers["LoadLibraryExW"] = self._load_library_ex
        p.api_handlers["GetProcAddress"] = self._get_proc
        p.api_handlers["VirtualAlloc"] = lambda proc: (proc.alloc(proc.arg(1)), 16)
        p.api_handlers["VirtualFree"] = lambda proc: (1, 12)
        for name in ("SHGetSpecialFolderPathA", "CreateDirectoryA", "CreateFileA", "ReadFile", "WriteFile",
                     "FlushFileBuffers", "CloseHandle", "MoveFileExA", "DeleteFileA", "GetLastError",
                     "GetFileAttributesA", "MultiByteToWideChar", "GetFileAttributesW", "MoveFileW",
                     "GetLocalTime", "SystemTimeToFileTime", "FileTimeToSystemTime"):
            p.api_handlers[name] = getattr(self, "_" + name)
        p.stub(WRITE_RECORD, self._write_record)
        p.stub(SLOT_FN, lambda proc: (self.slot, 0))
        self.host = p.alloc(16)
        p.put32(self.host, 8)
        p.put32(self.host + 4, SLOT_FN)

    def _load_library(self, proc):
        name = proc.cstring(proc.arg(0))
        return (FAKE_PARENTAGE if name.endswith("\\VVFP Parentage Export.dll") else 0), 4

    def _load_library_ex(self, proc):
        """By full path in the patcher's folder beside the executable, as the
        companion loads it (native/shared/patcher_files.h); nothing else."""
        name = proc.wstring(proc.arg(0))
        folder = proc.exe_path.decode("latin-1").rsplit("\\", 1)[0]
        wanted = folder + "\\Virtual Villagers Fun Patcher Files\\VVFP Parentage Export.dll"
        return (FAKE_PARENTAGE if name == wanted else 0), 12

    def _get_proc(self, proc):
        name = proc.cstring(proc.arg(1))
        return (WRITE_RECORD if proc.arg(0) == FAKE_PARENTAGE and name == "WriteVillageRecord" else 0), 8

    # A small in-memory file system for the companion's files (their exact
    # bytes and atomic writing are the files harness's; here only that they
    # are read and written when they should be).
    def _SHGetSpecialFolderPathA(self, proc):
        proc.write(proc.arg(1), b"C:\\Docs\0")
        return 1, 16

    def _CreateDirectoryA(self, proc):
        self.dirs.add(proc.cstring(proc.arg(0)).lower())
        return 1, 8

    # native/shared/data_subfolder.h asks what is at a path before choosing
    # between a file's folder and a loose copy an older build left.
    def _GetFileAttributesA(self, proc):
        path = proc.cstring(proc.arg(0))
        if path in self.files:
            return 0x80, 4                      # FILE_ATTRIBUTE_NORMAL
        if path.lower() in self.dirs:
            return 0x10, 4                      # FILE_ATTRIBUTE_DIRECTORY
        self.last_error = 2                     # ERROR_FILE_NOT_FOUND
        return 0xFFFFFFFF, 4

    # native/shared/save_layout.h renames a file an older build named otherwise (the roster's
    # "... Village Roster - Save S.dat") by its wide path, when only the old name exists.
    def _MultiByteToWideChar(self, proc):
        text = proc.cstring(proc.arg(2)) + "\0"
        if proc.arg(5):
            proc.write(proc.arg(4), text.encode("utf-16-le"))
        return len(text), 24

    def _GetFileAttributesW(self, proc):
        path = proc.wstring(proc.arg(0))
        if path in self.files:
            return 0x80, 4
        if path.lower() in self.dirs:
            return 0x10, 4
        self.last_error = 2
        return 0xFFFFFFFF, 4

    def _MoveFileW(self, proc):
        old, new = proc.wstring(proc.arg(0)), proc.wstring(proc.arg(1))
        if old not in self.files or new in self.files:
            return 0, 8
        self.files[new] = self.files.pop(old)
        return 1, 8

    def _CreateFileA(self, proc):
        path, disposition = proc.cstring(proc.arg(0)), proc.arg(4)
        if disposition == 3 and path not in self.files:        # OPEN_EXISTING
            self.last_error = 2
            return 0xFFFFFFFF, 28
        if disposition != 3:
            self.files[path] = bytearray()
        handle = 0x100 + 4 * len(self.handles)
        self.handles[handle] = [path, 0]
        return handle, 28

    def _ReadFile(self, proc):
        path, pos = self.handles[proc.arg(0)]
        data = bytes(self.files[path][pos:pos + proc.arg(2)])
        proc.write(proc.arg(1), data)
        proc.put32(proc.arg(3), len(data))
        self.handles[proc.arg(0)][1] = pos + len(data)
        return 1, 20

    def _WriteFile(self, proc):
        path, _ = self.handles[proc.arg(0)]
        self.files[path] += proc.read(proc.arg(1), proc.arg(2))
        proc.put32(proc.arg(3), proc.arg(2))
        return 1, 20

    def _FlushFileBuffers(self, proc):
        return 1, 4

    def _CloseHandle(self, proc):
        self.handles.pop(proc.arg(0), None)
        return 1, 4

    def _MoveFileExA(self, proc):
        self.files[proc.cstring(proc.arg(1))] = self.files.pop(proc.cstring(proc.arg(0)))
        return 1, 12

    def _DeleteFileA(self, proc):
        return (1 if self.files.pop(proc.cstring(proc.arg(0)), None) is not None else 0), 4

    def _GetLastError(self, proc):
        return self.last_error, 0

    def _GetLocalTime(self, proc):
        proc.write(proc.arg(0), struct.pack("<8H", 2026, 10, 5, 2, 12, 0, 0, 0))
        return 0, 4

    def _SystemTimeToFileTime(self, proc):
        proc.write(proc.arg(1), struct.pack("<Q", 134040000000000000))
        return 1, 8

    def _FileTimeToSystemTime(self, proc):
        proc.write(proc.arg(1), struct.pack("<8H", 2026, 10, 5, 2, 12, 0, 0, 0))
        return 1, 8

    def roster(self, slot: int) -> bytes | None:
        name = (f"C:\\Docs\\LDW\\Game\\Virtual Villagers Fun Patcher Data\\Unaccounted Villagers\\"
                f"Virtual Villagers {self.no} Villagers at Last Save - Save {slot}.dat")
        data = self.files.get(name)
        return bytes(data) if data is not None else None

    def _write_record(self, proc):
        before = proc.cstring(proc.arg(4)) if proc.arg(4) else ""
        after = proc.cstring(proc.arg(5)) if proc.arg(5) else ""
        self.logged.append(dict(game=proc.arg(0), kind=proc.arg(1), record=proc.arg(2), check=proc.arg(3),
                                before=before, after=after, detail=proc.arg(6), **lines(before + after)))
        return 1, 28

    def install(self) -> int:
        return self.p.export("VvfpCauseInstall", self.no, self.host)

    def tick(self) -> None:
        self.p.export("VvfpCauseTick", self.no)

    def stats(self) -> dict:
        values = struct.unpack(f"<{len(STAT_NAMES)}i", self.p.read(self.p.exports["VvfpCauseStats"], 4 * len(STAT_NAMES)))
        return dict(zip(STAT_NAMES, values))

    def force_roll(self, value: int) -> None:
        self.p.put32(self.p.exports["VvfpCauseRollTest"], value & 0xFFFFFFFF)

    def of_kind(self, kind: int) -> list[dict]:
        return [e for e in self.logged if e["kind"] == kind]

    def run(self, start: int, stop: int, **regs) -> None:
        p = self.p
        p.set_reg("esp", STACK)
        for name, value in regs.items():
            p.set_reg(name, value)
        p.run(start, stop)

    def saved_epilogue(self, site: int, slot: int, ok: int) -> None:
        """Run a save call's epilogue `pop edi; pop esi; ret 4` (the hook
        after the game's own save call) with al = saved, edi = slot."""
        p = self.p
        esp = STACK
        for k, value in enumerate((0, 0, 0x0D000000, slot)):
            p.put32(esp + 4 * k, value)
        p.set_reg("esp", esp)
        p.set_reg("eax", ok)
        p.set_reg("edi", slot)
        p.run(site, 0x0D000000)


def install_checks(test: unittest.TestCase, game: str, world=None) -> None:
    for mode in MODES:
        for everything in (False, True):
            g = Game(game, rendered(game, mode, everything))
            if world is not None:
                world(g)
            for d in manifest(game)["runtime_detours"]:
                va = int(d["va"], 16)
                test.assertEqual(g.p.read(va, len(bytes.fromhex(d["stock_bytes"]))),
                                 bytes.fromhex(d["stock_bytes"]), (game, mode, everything, d["va"]))
            test.assertEqual(g.install(), 1, (game, mode, everything))
            for d in manifest(game)["runtime_detours"]:
                test.assertEqual(g.p.read(int(d["va"], 16), 1), b"\xE9", (game, mode, everything, d["va"]))


def one_wrong_byte_checks(test: unittest.TestCase, game: str, world=None) -> None:
    for d in manifest(game)["runtime_detours"]:
        g = Game(game, rendered(game, "stock", True))
        if world is not None:
            world(g)
        va = int(d["va"], 16)
        g.p.write(va + 1, bytes([g.p.read(va + 1, 1)[0] ^ 0xFF]))
        test.assertEqual(g.install(), 0, (game, d["va"]))
        for other in manifest(game)["runtime_detours"]:
            if other is not d:
                test.assertNotEqual(g.p.read(int(other["va"], 16), 1), b"\xE9", (d["va"], other["va"]))


# ---- A child's grave: "Apprentice <job>" (A New Home, The Lost Children) ----
# The grave's job values and the popup's words for them.
V1_JOBS = {1: "Farmer", 2: "Parent", 3: "Scientist", 4: "Builder", 5: "Doctor"}
V2_JOBS = {1: "Farmer", 2: "Parent", 3: "Doctor", 4: "Scientist", 5: "Builder"}
# Ages at death in age units (20 a year): 2 years, 13y0, 13y19 (the last unit
# before 14), exactly 14y0, 14y1, 65.  Under 280 is a child.
APPRENTICE_AGES = (40, 260, 279, 280, 281, 1300)


def apprentice_cases(master: int) -> list[tuple[int, int, int]]:
    """(age, job, best value): every job at each rank's edges, a value under
    20, and no job."""
    values = (19, 20, 49, 50, master - 1, master)
    return [(age, job, value) for age in APPRENTICE_AGES for job in range(0, 6) for value in values
            if job or value == 50]


def apprentice_rank(case: tuple[int, int, int], master: int) -> str | None:
    age, job, value = case
    if job == 0 or value < 20:
        return None
    if age < 280:
        return "Apprentice"
    return "Trainee" if value < 50 else "Adept" if value < master else "Master"


def apprentice_screen(case, jobs: dict, master: int) -> str:
    """The popup's line: the game's own rank strings ("Trainee  " keeps its
    stock double space) and the job word."""
    rank = apprentice_rank(case, master)
    if rank is None:
        return "Untrained"
    return {"Apprentice": "Apprentice ", "Trainee": "Trainee  ", "Adept": "Adept ",
            "Master": "Master "}[rank] + jobs[case[1]]


def apprentice_log(case, jobs: dict, master: int) -> str:
    rank = apprentice_rank(case, master)
    return "Untrained" if rank is None else f"{rank} {jobs[case[1]]}"


# ---- A New Home -------------------------------------------------------------
V1 = dict(array_global=0x48B614, stride=0x3D8, present=0x28, selected=0x29, health=0x344, age=0x348,
          sex=0x350, name=0x370, skills=0x3BC, manager=0x3E010, graves=0xA31C, grave_stride=0x2C,
          grave_age=0x24, font=0x48B608)


class NewHome:
    """A New Home's villagers, manager and graves in the emulated process."""

    def __init__(self, g: Game):
        self.g = g
        p = g.p
        self.array = p.alloc(0x3E100)
        self.manager = p.alloc(0xB000)
        p.put32(V1["array_global"], self.array)
        p.put32(self.array + V1["manager"], self.manager)
        # The aging step's `this`: [esi] = manager, [esi+4] = array.
        self.step = p.alloc(16)
        p.put32(self.step, self.manager)
        p.put32(self.step + 4, self.array)

    def record(self, i: int) -> int:
        return self.array + i * V1["stride"]

    def villager(self, i: int, name: str, age: int, health: int, skills=(0, 0, 0, 0, 0)) -> int:
        """skills in storage order: Parenting, Building, Farming, Healing, Research."""
        r = self.record(i)
        p = self.g.p
        p.write(r, bytes(V1["stride"]))
        p.write(r + V1["present"], b"\x01")
        p.put32(r + V1["health"], health)
        p.put32(r + V1["age"], age)
        p.write(r + V1["name"], name.encode() + b"\0")
        for k, value in enumerate(skills):
            p.put32(r + V1["skills"] + 4 * k, value)
        return r

    def health(self, i: int) -> int:
        return struct.unpack("<i", self.g.p.read(self.record(i) + V1["health"], 4))[0]

    def grave(self, k: int) -> int:
        return self.manager + V1["graves"] + k * V1["grave_stride"]

    # The game's own instructions, from just before each site to just after.
    def old_age(self, i: int) -> None:
        self.g.run(0x42EF01, 0x42EF15, ebx=self.record(i), eax=0, ecx=1, edi=i * V1["stride"], esi=self.step)

    def drain(self, start: int, stop: int, i: int) -> None:
        self.g.run(start, stop, esi=self.step, edi=i * V1["stride"])

    def hunger(self, i: int) -> None:
        self.drain(0x42ECB4, 0x42ECC8, i)

    def no_food(self, i: int) -> None:
        self.drain(0x42ED34, 0x42ED48, i)

    def sickness(self, i: int) -> None:
        self.drain(0x42EDA0, 0x42EDB4, i)

    def injury(self, i: int, damage: int) -> None:
        """0x43A5B4: `sub [ebx], eax; mov eax, [esi+0x3E010]`."""
        self.g.run(0x43A5B4, 0x43A5BC, ebx=self.record(i) + V1["health"], eax=damage, esi=self.array)

    def bury(self, i: int, best_skill: int = 30, job: int = 4) -> int:
        """The burial branch of the action runner, 0x448F2F..0x449016: the
        game's own presence/health guard, record free and grave loop, and the
        hook after it.  Returns the grave slot it wrote (or -1)."""
        p = self.g.p
        before = [p.u32(self.grave(k) + V1["grave_age"]) for k in range(50)]
        burier = p.alloc(0x400)
        p.put32(burier + 0x344 - 0x2EC, i)
        p.stub(0x4393E0, lambda proc: (0, 0))
        def best(proc):
            proc.put32(proc.arg(1), job)
            return best_skill, 8
        p.stub(0x43B520, best)

        def sprintf(proc):
            text = proc.cstring(proc.arg(1)).encode("latin-1")
            proc.write(proc.arg(0), text + b"\0")
            return len(text), 0
        p.stub(0x44B23D, sprintf)
        self.g.run(0x448F2F, 0x449016, eax=i * V1["stride"], edi=self.array, esi=burier + 0x344)
        for k in range(50):
            if before[k] == 0 and p.u32(self.grave(k) + V1["grave_age"]) != 0:
                return k
        return -1

    def decay(self, i: int) -> None:
        self.g.run(0x42E9C3, 0x42E9C8, edi=i * V1["stride"], eax=self.array, esi=self.step)

    def popup_object(self, k: int, top: int = 100) -> int:
        p = self.g.p
        popup = p.alloc(0x100)
        p.put32(popup + 0x14, 200)
        p.put32(popup + 0x1C, 520)
        p.put32(popup + 0x18, top)
        p.put32(popup + 0x60, k)
        p.put32(popup + 0x64, 2)            # Done's id
        p.put32(popup + 0x74, self.manager)
        p.put32(popup + 0x7C, 0x0C300800)
        return popup

    def popup(self, k: int) -> list[tuple[str, int, int]]:
        """The grave popup's own Draw (0x436440), every line it draws:
        (text, x, y - top)."""
        p = self.g.p
        draws: list[tuple[str, int, int]] = []
        top = 100
        # The game's own English strings (its table at 0x487208).
        strings = {0x93: "Here Lies ", 0x94: "Job", 0x95: "Age", 0x54: "Untrained", 0x56: "Apprentice ", 0x57: "Trainee  ",
                   0x58: "Adept ", 0x59: "Master ", 0x5A: "Farmer", 0x5B: "Parent", 0x5C: "Builder",
                   0x5D: "Scientist", 0x5E: "Doctor"}
        pool = p.alloc(0x1000)
        where = {}
        for n, (key, text) in enumerate(strings.items()):
            where[key] = pool + n * 32
            p.write(pool + n * 32, text.encode() + b"\0")
        p.stub(0x408090, lambda proc: (0x0C300000, 0))
        p.stub(0x433970, lambda proc: (where[proc.arg(0)], 4))

        def sprintf(proc):
            fmt = proc.cstring(proc.arg(1))
            args = [proc.arg(2 + n) for n in range(4)]
            if fmt == "%s %i":
                text = proc.cstring(args[0]) + " " + str(struct.unpack("<i", struct.pack("<I", args[1]))[0])
            else:
                text = fmt.replace("%%", "%")
            proc.write(proc.arg(0), text.encode("latin-1") + b"\0")
            return len(text), 0
        p.stub(0x44B23D, sprintf)

        def draw(proc):
            draws.append((proc.cstring(proc.arg(0)), proc.arg(1), proc.arg(2) - top))
            return 0, 0x14
        p.stub(0x4094C0, draw)
        if not p.mapped(0x0C300000, 1):
            p.mu.mem_map(0x0C300000, 0x1000)
        p.call(0x436440, ecx=self.popup_object(k, top))
        return draws

    def open_popup(self, k: int) -> tuple[int, list]:
        """The popup constructor's end (0x436E5C..0x436E63), the hook there
        making the epitaph box with the game's widget calls (scripted, and
        recorded as (routine, args))."""
        p = self.g.p
        calls: list = []
        box = p.alloc(0x40)
        popup = self.popup_object(k)
        widget = {0x40C2C0: ("ctor", 7, box), 0x40BB00: ("colour", 2, 0), 0x40B9A0: ("rect", 1, 0),
                  0x40AB80: ("add", 1, 0), 0x40BB20: ("editable", 2, 0), 0x40BB30: ("set_text", 1, 0),
                  0x40BBA0: ("begin", 0, 0)}

        def make(va, name, n, result):
            def fn(proc):
                args = [proc.arg(j) for j in range(n)]
                if name == "set_text":
                    args = [proc.cstring(args[0])]
                if name == "rect":
                    args = [list(struct.unpack("<4i", proc.read(args[0], 16)))]
                calls.append((name, proc.reg("ecx"), args))
                return result, 4 * n
            p.stub(va, fn)
        for va, (name, n, result) in widget.items():
            make(va, name, n, result)
        p.stub(0x44AF03, lambda proc: (calls.append(("new", 0, [proc.arg(0)])) or box, 0))
        self.g.run(0x436E5C, 0x436E63, esi=popup)
        return popup, calls

    def done(self, popup: int, typed: str) -> None:
        """The popup's onEvent (0x436400) for Done, the box holding `typed`."""
        p = self.g.p

        def get_text(proc):
            data = typed.encode("latin-1")[: proc.arg(1) - 1]
            proc.write(proc.arg(0), data + b"\0")
            return 0, 8
        p.stub(0x40BB70, get_text)
        p.stub(0x40C9B0, lambda proc: (0, 0))
        p.call(0x436400, [8, 2], ecx=popup)


def vv1(mode: str = "stock", everything: bool = True, slot: int = 0) -> tuple[Game, NewHome]:
    g = Game("vv1", rendered("vv1", mode, everything), slot)
    world = NewHome(g)
    assert g.install() == 1
    return g, world


@unittest.skipUnless(STOCK["vv1"].is_file(), STOCK_ABSENT)
@unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
class NewHomeCauseOfDeath(unittest.TestCase):
    def test_install_writes_every_site_in_every_mode_alone_and_with_everything(self):
        install_checks(self, "vv1", NewHome)

    def test_one_wrong_byte_anywhere_installs_nothing(self):
        one_wrong_byte_checks(self, "vv1", NewHome)

    def test_each_cause_reaches_the_death_record_written_at_the_burial(self):
        for mode in MODES:
            g, w = vv1(mode)
            cases = []
            w.villager(3, "Olda", 1500, 40)
            w.old_age(3)
            cases.append((3, "Olda", 1500, "Old age"))
            w.villager(4, "Sicky", 700, 1)
            g.p.put32(w.record(4) + 0x354, 1)
            w.sickness(4)
            cases.append((4, "Sicky", 700, "Disease"))
            w.villager(5, "Hungry", 800, 1)
            w.hunger(5)
            cases.append((5, "Hungry", 800, "Starvation"))
            w.villager(6, "Empty", 900, 1)
            w.no_food(6)
            cases.append((6, "Empty", 900, "Starvation"))
            w.villager(7, "Worker", 1000, 5)
            w.injury(7, 9)
            cases.append((7, "Worker", 1000, "Work accident"))
            w.villager(8, "Exact", 1100, 6)     # an injury to exactly 0 kills too
            w.injury(8, 6)
            cases.append((8, "Exact", 1100, "Work accident"))
            self.assertEqual(g.logged, [], "nothing is logged until the death is final")
            for i, _, _, _ in cases:
                w.bury(i)
            deaths = g.of_kind(DEATH)
            self.assertEqual([(e["record"], e["Age at death"], e["Cause of death"]) for e in deaths],
                             [(w.record(i), str(age), cause) for i, _, age, cause in cases], mode)
            self.assertTrue(all(e["check"] == 1 and e["detail"] == 1 for e in deaths))
            self.assertEqual(g.stats()["deaths"], 6)

    def test_a_change_that_does_not_kill_records_nothing(self):
        g, w = vv1()
        w.villager(4, "Sicky", 700, 2)
        w.sickness(4)
        w.villager(7, "Worker", 1000, 10)
        w.injury(7, 9)
        w.villager(8, "Bones", 1000, 0)      # already dead
        w.old_age(8)
        w.injury(8, 3)
        self.assertEqual((w.health(4), w.health(7)), (1, 1))
        self.assertEqual(g.stats()["deaths"], 0)
        w.bury(8)
        self.assertEqual(g.of_kind(DEATH)[0]["Cause of death"][:14], "(not recorded:")

    def test_an_unreported_death_is_unknown_causes_only_for_a_villager_seen_alive(self):
        g, w = vv1()
        w.villager(10, "Eventa", 600, 50)
        w.villager(11, "Loaded", 650, 0)      # a body the village was loaded with
        g.tick()
        g.p.put32(w.record(10) + V1["health"], 0)   # an island event's store
        g.tick()
        g.tick()
        self.assertEqual(g.stats()["unhooked"], 1)
        w.bury(10)
        w.bury(11)
        causes = [e["Cause of death"] for e in g.of_kind(DEATH)]
        self.assertEqual(causes[0], "Unknown causes")
        self.assertTrue(causes[1].startswith("(not recorded:"))

    def test_the_death_record_carries_the_grave_and_the_popup_shows_cause_and_quotes(self):
        for mode in MODES:
            g, w = vv1(mode)
            g.force_roll(1)
            w.villager(3, "Olda", 1500, 40, skills=(10, 70, 20, 30, 40))
            w.old_age(3)
            k = w.bury(3, best_skill=70, job=4)
            self.assertEqual(k, 0, mode)
            self.assertEqual(g.p.read(w.record(3) + V1["present"], 1), b"\x00")
            death = g.of_kind(DEATH)[0]
            self.assertEqual((death["Grave"], death["Epitaph"]), ("Adept Builder", "Strong Arms, Big Heart"), mode)
            lines_ = w.popup(k)
            texts = [t for t, _, _ in lines_]
            self.assertIn("Here Lies Olda", texts, mode)
            self.assertIn(("Old age", 0xD7), [(t, y) for t, _, y in lines_], mode)
            # The epitaph's quotes, where The Lost Children draws its own.
            self.assertEqual([(x, y) for t, x, y in lines_ if t == "\""], [(200 + 0x1C, 0x46), (520 - 0x1C, 0x46)])
            # Same centre as the game's own lines.
            self.assertEqual(len({x for t, x, _ in lines_ if t != "\""}), 1, mode)
            self.assertEqual(g.stats()["graves_set"], 1, mode)

    def test_the_epitaph_box_is_made_with_the_games_widget_and_done_keeps_an_edit(self):
        g, w = vv1(slot=2)
        g.tick()
        g.force_roll(0)
        w.villager(3, "Olda", 1500, 40, skills=(0, 0, 0, 0, 60))
        w.old_age(3)
        k = w.bury(3, best_skill=60, job=3)
        popup, calls = w.open_popup(k)
        self.assertEqual([c[0] for c in calls],
                         ["new", "ctor", "colour", "rect", "add", "editable", "set_text", "begin"])
        ctor = calls[1][2]
        self.assertEqual((ctor[0], ctor[1], ctor[2], ctor[4], ctor[5]), (popup, 0xA0, 0x46, 1, 0))
        self.assertEqual(calls[3][2], [[0x20, 0x46, 0x11C, 0x5A]])
        self.assertEqual(calls[4][1], popup)
        self.assertEqual(calls[5][2], [1, 31])
        self.assertEqual(calls[6][2], ["Dedicated Student"])
        self.assertEqual(g.p.u32(popup + 0x5C), 0x122, "the constructor's own store still runs")
        w.done(popup, "Dedicated Student")          # unchanged: nothing
        self.assertEqual(g.of_kind(EPITAPH), [])
        popup, _ = w.open_popup(k)
        w.done(popup, "Our Wise \xc9lder")
        change = g.of_kind(EPITAPH)
        self.assertEqual(len(change), 1)
        self.assertEqual((change[0]["Old epitaph"], change[0]["New epitaph"], change[0]["Grave"]),
                         ("Dedicated Student", "Our Wise ?lder", "Adept Scientist"))
        self.assertEqual((change[0]["check"], change[0]["detail"]), (0, 0))
        popup, calls = w.open_popup(k)
        self.assertEqual(calls[6][2], ["Our Wise \xc9lder"], "the box opens with the kept text")

    def test_spaces_typed_around_an_unchanged_epitaph_are_not_a_change(self):
        """Live, v1.35.59: three stray Space presses in the open epitaph box
        made an "Epitaph changed" record whose old and new epitaph read the
        same.  Spaces before or after the same text change nothing: no
        record, and the grave keeps its own epitaph."""
        g, w = vv1(slot=2)
        g.tick()
        g.force_roll(0)
        w.villager(3, "Olda", 1500, 40, skills=(0, 0, 0, 0, 60))
        w.old_age(3)
        k = w.bury(3, best_skill=60, job=3)
        for typed in ("Dedicated Student   ", "  Dedicated Student", " Dedicated Student "):
            popup, _ = w.open_popup(k)
            w.done(popup, typed)
            self.assertEqual(g.of_kind(EPITAPH), [], repr(typed))
            popup, calls = w.open_popup(k)
            self.assertEqual(calls[6][2], ["Dedicated Student"], repr(typed))
        popup, _ = w.open_popup(k)
        w.done(popup, "Dedicated  Student")           # a space inside is a real edit
        self.assertEqual([(e["Old epitaph"], e["New epitaph"]) for e in g.of_kind(EPITAPH)],
                         [("Dedicated Student", "Dedicated  Student")])

    def test_graves_from_before_get_an_epitaph_and_no_cause(self):
        g, w = vv1(slot=2)
        g.tick()
        g.p.write(w.grave(5), b"Ancestor\0")
        g.p.put32(w.grave(5) + V1["grave_age"], 1300)
        texts = [t for t, _, _ in w.popup(5)]
        self.assertEqual([t for t in texts if t != "\""], ["Here Lies Ancestor", "Job", "Untrained", "Age 65"])
        self.assertEqual(texts.count("\""), 2)
        _, calls = w.open_popup(5)
        self.assertEqual(calls[6][2], ["Respected Citizen"])

    def test_a_villager_buried_at_age_0_has_a_grave(self):
        # The owner, 2026-10-09: "for all 5 games, 0 is a valid value for head, body and age!!!!"  The
        # game's grave loop wrote a grave (its counter says so); its age 0 is a real age, never "the
        # graveyard was full".
        for mode in MODES:
            g, w = vv1(mode)
            w.villager(3, "Babe", 0, 5)
            w.injury(3, 9)
            w.bury(3, best_skill=30, job=4)
            self.assertEqual(bytes(g.p.read(w.grave(0), 5)), b"Babe\0", mode)
            (death,) = g.of_kind(DEATH)
            self.assertEqual((death["Age at death"], death["Grave"]), ("0", "Apprentice Builder"), mode)
            self.assertNotIn("graveyard was full", death["Grave"], mode)

    def test_a_removed_body_is_a_death_with_no_grave(self):
        g, w = vv1()
        w.villager(12, "Gone", 1500, 30)
        w.old_age(12)
        w.decay(12)
        self.assertEqual(g.p.read(w.record(12) + V1["present"], 1), b"\x00")
        death = g.of_kind(DEATH)
        self.assertEqual([(e["Cause of death"], e["Grave"], e["Epitaph"]) for e in death],
                         [("Old age", NO_GRAVE, "(none)")])

    def test_a_bodys_cause_follows_it_when_the_load_packs_the_records(self):
        g, w = vv1(slot=2)
        g.tick()
        w.villager(11, "Before", 500, 50)
        w.villager(12, "Packed", 1500, 30)
        w.old_age(12)
        # The game's load: record 11 freed, 12 moved down to 11.
        g.p.write(w.record(11), g.p.read(w.record(12), V1["stride"]))
        g.p.write(w.record(12), bytes(V1["stride"]))
        g.tick()
        w.bury(11)
        self.assertEqual(g.of_kind(DEATH)[0]["Cause of death"], "Old age")

    def test_the_epitaph_rule(self):
        cases = [
            # (age, grave job, value), roll -> epitaph (A New Home's jobs: 1 Farmer, 2 Parent,
            # 3 Scientist, 4 Builder, 5 Doctor)
            ((300, 4, 90), 0, "Curious and Playful"),
            ((300, 0, 0), 1, "Loving and Special"),
            ((400, 0, 0), 0, "Respected Citizen"),
            ((400, 1, 5), 0, "Child of the Earth"),
            ((400, 1, 5), 1, "Nature's Friend"),
            ((400, 2, 7), 0, "Parent, Teacher, Friend"),
            ((400, 2, 7), 1, "Dedicated to Children"),
            ((400, 5, 9), 0, "Guardian of Health"),
            ((400, 5, 9), 1, "Dedicated to Others"),
            ((400, 3, 3), 0, "Dedicated Student"),
            ((400, 3, 3), 1, "Inspired Inventor"),
            ((400, 4, 4), 0, "Inspired Architect"),
            ((400, 4, 4), 1, "Strong Arms, Big Heart"),
            ((359, 4, 9), 0, "Curious and Playful"),
            ((360, 4, 9), 0, "Inspired Architect"),
        ]
        g, w = vv1(slot=2)
        g.tick()
        for n, ((age, job, value), roll, want) in enumerate(cases):
            g.force_roll(roll)
            k = 10 + n
            g.p.write(w.grave(k), f"V{n}".encode() + b"\0")
            g.p.put32(w.grave(k) + 0x1C, value)
            g.p.put32(w.grave(k) + 0x20, job)
            g.p.put32(w.grave(k) + V1["grave_age"], age)
            _, calls = w.open_popup(k)
            self.assertEqual(calls[6][2], [want], (age, job, value, roll))

    def test_a_childs_grave_names_the_job_as_an_apprentice(self):
        """The owner: "for vv1 graves: the job for children should say
        'Apprentice _______' instead of trainee/adept/master etc";
        "Children = less than 14 years old" -- under 280 age units at death,
        the grave's own age."""
        g, w = vv1(slot=2)
        g.tick()
        for n, case in enumerate(apprentice_cases(master=90)):
            age, job, value = case
            k = n % 50
            g.p.write(w.grave(k), f"C{n}".encode() + b"\0")
            g.p.put32(w.grave(k) + 0x1C, value)
            g.p.put32(w.grave(k) + 0x20, job)
            g.p.put32(w.grave(k) + V1["grave_age"], age)
            texts = [t for t, _, _ in w.popup(k)]
            screen = texts[texts.index("Job") + 1]
            self.assertEqual(screen, apprentice_screen(case, V1_JOBS, 90), case)
            # The log's Grave line names the same rank and job (the Epitaph
            # changed record carries it).
            popup, _ = w.open_popup(k)
            w.done(popup, f"Changed {n}")
            self.assertEqual(g.of_kind(EPITAPH)[-1]["Grave"], apprentice_log(case, V1_JOBS, 90), case)

    def test_a_childs_burial_is_an_apprentice_in_every_mode(self):
        for mode in MODES:
            g, w = vv1(mode)
            for i, age in ((3, 279), (4, 280), (5, 260)):
                w.villager(i, f"Kid{i}", age, 40)
                w.old_age(i)
            w.villager(6, "Weak", 100, 40)
            w.old_age(6)
            graves = [w.bury(3, best_skill=70, job=4), w.bury(4, best_skill=70, job=4),
                      w.bury(5, best_skill=20, job=1), w.bury(6, best_skill=19, job=1)]
            deaths = g.of_kind(DEATH)
            self.assertEqual([e["Grave"] for e in deaths],
                             ["Apprentice Builder", "Adept Builder", "Apprentice Farmer", "Untrained"], mode)
            # The children's epitaphs are still the children's (under 18 years).
            self.assertTrue(all(e["Epitaph"] in ("Curious and Playful", "Loving and Special") for e in deaths), mode)
            screens = []
            for k in graves:
                texts = [t for t, _, _ in w.popup(k)]
                screens.append(texts[texts.index("Job") + 1])
            self.assertEqual(screens, ["Apprentice Builder", "Adept Builder", "Apprentice Farmer", "Untrained"], mode)

    def test_the_mysterious_face_and_the_book_are_disappearances(self):
        g, w = vv1()
        w.villager(4, "Curious", 600, 80)
        g.run(0x41979D, 0x4197A7, edx=4 * V1["stride"], eax=w.record(0), ebx=0, esi=w.array)
        w.villager(5, "Reader", 700, 80)
        g.p.put32(STACK, 0)
        g.run(0x41A272, 0x41A277, ecx=5 * V1["stride"], edx=w.record(0), ebx=0)
        gone = g.of_kind(DISAPPEARED)
        self.assertEqual([(e["record"], e["Age"], e["What happened"]) for e in gone], [
            (w.record(4), "600", "Took a closer look at The Mysterious Face and was never heard from again"),
            (w.record(5), "700", "Read The Book and left the village"),
        ])
        self.assertEqual(g.p.read(w.record(4) + V1["present"], 1), b"\x00")
        self.assertEqual(g.stats()["departed"], 2)

    def test_the_creators_report_arrivals_and_the_saves_writer_reconciles(self):
        g, w = vv1()
        w.villager(6, "Newborn", 0, 100)
        g.run(0x43C39B, 0x43C3A2, esi=w.record(6), ebp=0)
        w.villager(7, "Twin", 0, 100)
        g.run(0x43C888, 0x43C88E, esi=w.record(7), ebx=0)
        self.assertEqual(g.stats()["arrived"], 2)
        # The file writer's success epilogue: the village's 0xABDC-byte write.
        for size, slot, written, expected in ((0xABDC, 2, 0, False), (0xC0, 2, 1, False),
                                              (0xABDC, 6, 1, False), (0xABDC, 2, 1, True)):
            esp = STACK
            for k, value in enumerate((0, 0, 0)):
                g.p.put32(esp + 4 * k, value)
            g.p.put32(esp + 0x20C, 0x0D000000)
            g.p.put32(esp + 0x214, size)
            g.p.put32(esp + 0x218, slot)
            g.p.set_reg("esp", esp)
            g.p.set_reg("ebx", written)
            g.p.run(0x40322A, 0x0D000000)
            self.assertEqual(g.roster(slot) is not None, expected, (size, slot, written))
        self.assertEqual(struct.unpack_from("<4I", g.roster(2)), (0x31524356, 2, 1, 2))

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_the_custom_island_events_disappears_and_a_noted_birth_reach_the_companion(self):
        g, w = vv1()
        w.villager(3, "Vanisher", 640, 70)
        g.p.export("VvfpCauseVanished", 1, 3)               # still here: nothing
        self.assertEqual(g.of_kind(DISAPPEARED), [])
        g.p.write(w.record(3) + V1["present"], b"\x00")     # the event's own store
        g.p.export("VvfpCauseVanished", 1, 3)
        g.p.export("VvfpCauseVanished", 2, 3)               # another game: nothing
        self.assertEqual([(e["record"], e["What happened"]) for e in g.of_kind(DISAPPEARED)],
                         [(w.record(3), "Disappeared in a custom island event")])
        w.villager(4, "Born", 0, 100)
        g.p.export("VvfpCauseNoteArrival", 1, w.record(4))
        self.assertEqual(g.stats()["arrived"], 1)


# ---- The Lost Children ------------------------------------------------------
V2 = dict(pool_global=0x499F24, stride=0xE48C, present=0x30, selected=0x31, health=0x52C, age=0x530,
          name=0x564, skills=0x7E4, totem=0x558, world=0xE574D4, graves=0x2EB0C, grave_stride=0x7C,
          grave_age=0x74)


class LostChildren:
    def __init__(self, g: Game):
        self.g = g
        p = g.p
        self.pool = p.alloc(V2["world"] + 0x100)
        self.world = p.alloc(0x31000)
        p.put32(V2["pool_global"], self.pool)
        p.put32(self.pool + V2["world"], self.world)
        self.step = p.alloc(16)
        p.put32(self.step, self.world)
        p.put32(self.step + 4, self.pool)

    def record(self, i: int) -> int:
        return self.pool + i * V2["stride"]

    def villager(self, i: int, name: str, age: int, health: int) -> int:
        r = self.record(i)
        p = self.g.p
        p.write(r, bytes(0x900))
        p.write(r + V2["present"], b"\x01")
        p.put32(r + V2["health"], health)
        p.put32(r + V2["age"], age)
        p.write(r + V2["name"], name.encode() + b"\0")
        return r

    def health(self, i: int) -> int:
        return struct.unpack("<i", self.g.p.read(self.record(i) + V2["health"], 4))[0]

    def grave(self, k: int) -> int:
        return self.world + V2["graves"] + k * V2["grave_stride"]

    def old_age(self, i: int) -> None:
        self.g.run(0x43BDEA, 0x43BDFE, ebx=self.record(i), eax=0, ecx=1)

    def sickness(self, i: int) -> None:
        self.g.run(0x43BC39, 0x43BC4D, esi=self.step, edi=i * V2["stride"])

    def hunger(self, i: int) -> None:
        self.g.run(0x43BAE1, 0x43BAF5, esi=self.step, edi=i * V2["stride"])

    def no_food(self, i: int) -> None:
        self.g.run(0x43BB7B, 0x43BB87, esi=self.step, edi=i * V2["stride"])

    def injury(self, i: int, damage: int) -> None:
        self.g.run(0x462AD9, 0x462AE1, edi=self.record(i) + V2["health"], eax=damage, esi=self.pool)

    def bury(self, i: int, best_skill: int = 30, job: int | None = None) -> int:
        """The burial's grave loop, 0x465042..0x46533B (the record already
        freed by 0x46503B, as the game does just before), and the hook
        after it.  The best-skill routine (0x44B4D0: index, &job) is
        scripted: it returns `best_skill` and, given one, writes `job`."""
        p = self.g.p
        before = [p.u32(self.grave(k) + V2["grave_age"]) for k in range(50)]
        burier = p.alloc(0x100)
        p.put32(burier + 0x60, i)
        p.write(self.record(i) + V2["present"], b"\x00")

        def best(proc):
            if job is not None:
                proc.put32(proc.arg(1), job)
            return best_skill, 8
        p.stub(0x44B4D0, best)
        p.stub(0x4031A0, lambda proc: (0, 0))
        strings = p.alloc(0x100)
        p.write(strings, b"Respected Citizen\0")
        p.stub(0x441680, lambda proc: (strings, 4))

        def sprintf(proc):
            text = proc.cstring(proc.arg(1)).encode("latin-1")
            proc.write(proc.arg(0), text + b"\0")
            return len(text), 0
        p.stub(0x4682BD, sprintf)
        self.g.run(0x465040, 0x46533B, esi=self.pool, edi=burier, ebx=0)
        for k in range(50):
            if before[k] == 0 and p.u32(self.grave(k) + V2["grave_age"]) != 0:
                return k
        return -1

    def decay(self, i: int) -> None:
        self.g.run(0x43B78D, 0x43B792, eax=self.pool, edi=i * V2["stride"], esi=self.step)

    def panel_object(self, k: int, top: int = 100) -> int:
        p = self.g.p
        textbox = p.alloc(0x40)
        vtable = p.alloc(0x40)
        ret = p.alloc(0x10)
        p.write(ret, b"\xC3")
        p.put32(textbox, vtable)
        p.put32(vtable + 0xC, ret)
        panel = p.alloc(0x100)
        p.put32(panel + 0x14, 200)
        p.put32(panel + 0x1C, 520)
        p.put32(panel + 0x18, top)
        p.put32(panel + 0x60, k)
        p.put32(panel + 0x68, 2)
        p.put32(panel + 0x78, self.world)
        p.put32(panel + 0x80, 0x0C300800)
        p.put32(panel + 0x84, textbox)
        return panel

    def panel(self, k: int) -> list[tuple[str, int, int]]:
        p = self.g.p
        draws: list[tuple[str, int, int]] = []
        top = 100
        # The panel's strings (English, from the game's own table): "Here
        # Lies ", "Job", "Age", the ranks and the job words; any other "Age".
        strings = {0xCF: "Here Lies ", 0xD0: "Job", 0xD1: "Age", 0x81: "Untrained", 0x83: "Apprentice ",
                   0x84: "Trainee  ", 0x85: "Adept ", 0x86: "Master ", 0x88: "Farmer", 0x89: "Parent",
                   0x8A: "Builder", 0x8B: "Scientist", 0x8C: "Doctor"}
        pool = p.alloc(0x1000)
        where = {}
        for n, (key, text) in enumerate(strings.items()):
            where[key] = pool + n * 32
            p.write(pool + n * 32, text.encode() + b"\0")
        p.stub(0x408320, lambda proc: (0x0C300000, 0))
        p.stub(0x441680, lambda proc: (where.get(proc.arg(0), where[0xD1]), 4))

        def sprintf(proc):
            fmt = proc.cstring(proc.arg(1))
            if fmt == "%s %i":
                text = proc.cstring(proc.arg(2)) + " " + str(proc.arg(3))
            elif "%" in fmt:
                text = fmt.replace("%s", proc.cstring(proc.arg(2)))
            else:
                text = fmt
            proc.write(proc.arg(0), text.encode("latin-1") + b"\0")
            return len(text), 0
        p.stub(0x4682BD, sprintf)

        def draw(proc):
            draws.append((proc.cstring(proc.arg(0)), proc.arg(1), proc.arg(2) - top))
            return 0, 0x14
        p.stub(0x4096B0, draw)
        p.stub(0x40C510, lambda proc: (0, 0))
        p.call(0x444490, ecx=self.panel_object(k, top))
        return draws

    def done(self, k: int, typed: str) -> None:
        """The panel's onEvent (0x444420) for Done, its box holding `typed`:
        the game's own copy into the grave (0x40C550 scripted as the box's
        getText)."""
        p = self.g.p

        def get_text(proc):
            data = typed.encode("latin-1")[: proc.arg(1) - 1]
            proc.write(proc.arg(0), data + b"\0")
            return 0, 8
        p.stub(0x40C550, get_text)
        p.stub(0x40D390, lambda proc: (0, 0))
        p.call(0x444420, [8, 2], ecx=self.panel_object(k))


def vv2(mode: str = "stock", everything: bool = True) -> tuple[Game, LostChildren]:
    g = Game("vv2", rendered("vv2", mode, everything))
    world = LostChildren(g)
    assert g.install() == 1
    return g, world


@unittest.skipUnless(STOCK["vv2"].is_file(), STOCK_ABSENT)
@unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
class LostChildrenCauseOfDeath(unittest.TestCase):
    def test_install_writes_every_site_in_every_mode_alone_and_with_everything(self):
        install_checks(self, "vv2", LostChildren)

    def test_one_wrong_byte_anywhere_installs_nothing(self):
        one_wrong_byte_checks(self, "vv2", LostChildren)

    def test_each_cause_reaches_the_death_record_written_at_the_burial(self):
        for mode in MODES:
            g, w = vv2(mode)
            w.villager(3, "Olda", 1500, 40)
            w.old_age(3)
            w.villager(4, "Sicky", 700, 1)
            w.sickness(4)
            w.villager(5, "Hungry", 800, 1)
            w.hunger(5)
            w.villager(6, "Empty", 900, 1)
            w.no_food(6)
            w.villager(7, "Worker", 1000, 5)
            w.injury(7, 9)
            w.villager(8, "Fine", 1000, 50)
            w.injury(8, 9)
            self.assertEqual(w.health(8), 41)
            for i in (3, 4, 5, 6, 7):
                w.bury(i)
            self.assertEqual([(e["record"], e["Cause of death"], e["Epitaph"]) for e in g.of_kind(DEATH)], [
                (w.record(3), "Old age", "Respected Citizen"),
                (w.record(4), "Disease", "Respected Citizen"),
                (w.record(5), "Starvation", "Respected Citizen"),
                (w.record(6), "Starvation", "Respected Citizen"),
                (w.record(7), "Work accident", "Respected Citizen"),
            ], mode)

    def test_a_totem_is_never_a_death(self):
        g, w = vv2()
        w.villager(9, "Statue", 900, 50)
        g.p.write(w.record(9) + V2["totem"], b"\x01")
        g.tick()
        g.p.put32(w.record(9) + V2["health"], 0)
        g.tick()
        self.assertEqual(g.stats()["deaths"], 0)

    def test_the_grave_shows_the_cause_at_the_later_games_height_and_keeps_its_own_epitaph(self):
        for mode in MODES:
            g, w = vv2(mode)
            w.villager(3, "Olda", 1500, 40)
            w.old_age(3)
            k = w.bury(3)
            self.assertGreaterEqual(k, 0)
            lines_ = w.panel(k)
            self.assertIn(("Old age", 0xD7), [(t, y) for t, _, y in lines_], mode)
            self.assertIn(("Age 75", 0xB4), [(t, y) for t, _, y in lines_], mode)
            # The game's own quotes only: no epitaph from here.
            self.assertEqual([t for t, _, _ in lines_ if t.startswith("\"")], ["\"", "\""], mode)
            self.assertEqual(g.stats()["draws"], 1, mode)
            self.assertEqual(bytes(g.p.read(w.grave(k) + 0x19, 18)), b"Respected Citizen\0")

    def test_a_villager_buried_at_age_0_has_a_grave(self):
        # The owner, 2026-10-09: 0 is a valid age in all five games -- a grave at age 0 is a grave.
        for mode in MODES:
            g, w = vv2(mode)
            w.villager(3, "Babe", 0, 5)
            w.injury(3, 9)
            w.bury(3, best_skill=30, job=4)
            self.assertEqual(bytes(g.p.read(w.grave(0), 5)), b"Babe\0", mode)
            (death,) = g.of_kind(DEATH)
            self.assertEqual(death["Age at death"], "0", mode)
            self.assertTrue(death["Grave"].startswith("Apprentice "), (mode, death["Grave"]))

    def test_an_edited_epitaph_is_an_epitaph_changed_record(self):
        g, w = vv2()
        w.villager(3, "Olda", 1500, 40)
        w.old_age(3)
        k = w.bury(3)
        w.done(k, "Respected Citizen")
        self.assertEqual(g.of_kind(EPITAPH), [])
        w.done(k, "Mother of Many")
        self.assertEqual(bytes(g.p.read(w.grave(k) + 0x19, 15)), b"Mother of Many\0")
        change = g.of_kind(EPITAPH)
        self.assertEqual([(e["Old epitaph"], e["New epitaph"], e["Age at death"]) for e in change],
                         [("Respected Citizen", "Mother of Many", "1500")])

    def test_spaces_typed_around_an_unchanged_epitaph_are_not_a_change(self):
        g, w = vv2()
        w.villager(3, "Olda", 1500, 40)
        w.old_age(3)
        k = w.bury(3)
        for typed in ("Respected Citizen   ", "  Respected Citizen", " Respected Citizen ", "Respected Citizen"):
            w.done(k, typed)
            self.assertEqual(g.of_kind(EPITAPH), [], repr(typed))
        w.done(k, "Respected  Citizen")             # a space inside is a real edit
        self.assertEqual([(e["Old epitaph"], e["New epitaph"]) for e in g.of_kind(EPITAPH)],
                         [("Respected Citizen", "Respected  Citizen")])

    def test_a_name_that_fills_the_record_field_still_matches_its_grave(self):
        """The record's name field is 0x18 bytes and the burial copies it
        with sprintf to its terminator: a 24-letter name carries the bytes
        after the field into the 0x19-byte grave field.  The grave must still
        be recognised as that villager's."""
        g, w = vv2()
        r = w.villager(5, "A" * 24, 1500, 40)
        g.p.write(r + V2["name"] + 0x18, b"ZZ\0")
        w.old_age(5)
        k = w.bury(5)
        self.assertEqual(bytes(g.p.read(w.grave(k), 25)), b"A" * 24 + b"Z")
        self.assertIn(("Old age", 0xD7), [(t, y) for t, _, y in w.panel(k)])

    def test_graves_from_before_show_no_cause_and_a_removed_body_has_no_grave(self):
        g, w = vv2()
        g.p.write(w.grave(4), b"Ancestor\0")
        g.p.put32(w.grave(4) + V2["grave_age"], 1300)
        self.assertNotIn(0xD7, [y for _, _, y in w.panel(4)])
        w.villager(12, "Gone", 1500, 30)
        w.old_age(12)
        w.decay(12)
        self.assertEqual([(e["Cause of death"], e["Grave"]) for e in g.of_kind(DEATH)], [("Old age", NO_GRAVE)])

    def test_a_childs_grave_names_the_job_as_an_apprentice(self):
        """The owner: "and vv2 graves"; "Children = less than 14 years old"."""
        g, w = vv2()
        for n, case in enumerate(apprentice_cases(master=88)):
            age, job, value = case
            k = n % 50
            g.p.write(w.grave(k), f"C{n}".encode() + b"\0")
            g.p.write(w.grave(k) + 0x19, b"Respected Citizen\0")
            g.p.put32(w.grave(k) + 0x6C, value)
            g.p.put32(w.grave(k) + 0x70, job)
            g.p.put32(w.grave(k) + V2["grave_age"], age)
            texts = [t for t, _, _ in w.panel(k)]
            screen = texts[texts.index("Job") + 1]
            self.assertEqual(screen, apprentice_screen(case, V2_JOBS, 88), case)
            w.done(k, f"Changed {n}")
            self.assertEqual(g.of_kind(EPITAPH)[-1]["Grave"], apprentice_log(case, V2_JOBS, 88), case)

    def test_a_childs_burial_is_an_apprentice_in_every_mode(self):
        for mode in MODES:
            g, w = vv2(mode)
            for i, age in ((3, 279), (4, 280), (5, 260)):
                w.villager(i, f"Kid{i}", age, 40)
                w.old_age(i)
            graves = [w.bury(3, best_skill=70, job=5), w.bury(4, best_skill=70, job=5),
                      w.bury(5, best_skill=20, job=3)]
            self.assertEqual([e["Grave"] for e in g.of_kind(DEATH)],
                             ["Apprentice Builder", "Adept Builder", "Apprentice Doctor"], mode)
            screens = []
            for k in graves:
                texts = [t for t, _, _ in w.panel(k)]
                screens.append(texts[texts.index("Job") + 1])
            self.assertEqual(screens, ["Apprentice Builder", "Adept Builder", "Apprentice Doctor"], mode)

    def test_the_mission_and_the_voices_are_disappearances_and_the_stranger_is_not(self):
        g, w = vv2()
        w.villager(4, "Sailor", 300, 90)
        g.run(0x433E9B, 0x433EA0, eax=w.record(4), esi=0)
        w.villager(5, "Listener", 500, 90)
        g.run(0x4208FF, 0x420904, ecx=5 * V2["stride"], edx=w.pool, ebx=0)
        # The Strange Request's stranger: made by its setup, taken by either outcome.
        w.villager(6, "Biggles", 600, 90)
        g.run(0x44C84F, 0x44C856, esi=w.record(6))
        holder = g.p.alloc(0x6000)
        g.run(0x41F963, 0x41F969, eax=6, esi=holder)
        g.run(0x4208FF, 0x420904, ecx=6 * V2["stride"], edx=w.pool, ebx=0)
        gone = g.of_kind(DISAPPEARED)
        self.assertEqual([(e["record"], e["What happened"]) for e in gone], [
            (w.record(4), "Sailed off for the south shore on A Dangerous Mission"),
            (w.record(5), "Investigated The Voices In The Brush and was never seen again"),
        ])

    def test_a_load_over_the_strangers_record_brings_a_villager_of_the_tribe(self):
        """The Strange Request's stranger is not the tribe's while he holds his
        record.  The game's load refills every record in one call, with no
        creator and no frame between, so a villager loaded into his record
        was taken for him: her disappearance went unlogged."""
        for same_slot in (True, False):
            g, w = vv2()
            g.slot = 1
            w.villager(6, "Biggles", 600, 90)
            g.run(0x44C84F, 0x44C856, esi=w.record(6))
            g.run(0x41F963, 0x41F969, eax=6, esi=g.p.alloc(0x6000))
            g.tick()                                   # the village, the stranger on screen
            if not same_slot:
                g.slot = 2
            w.villager(6, "Mila", 500, 90)             # the load: someone of the tribe in his record
            g.tick()
            g.run(0x4208FF, 0x420904, ecx=6 * V2["stride"], edx=w.pool, ebx=0)
            gone = g.of_kind(DISAPPEARED)
            self.assertEqual([e["record"] for e in gone], [w.record(6)], same_slot)
        # Another village whose villager in that record has his very name.
        g, w = vv2()
        g.slot = 1
        w.villager(6, "Biggles", 600, 90)
        g.run(0x44C84F, 0x44C856, esi=w.record(6))
        g.run(0x41F963, 0x41F969, eax=6, esi=g.p.alloc(0x6000))
        g.tick()
        g.slot = 2
        w.villager(6, "Biggles", 300, 90)
        g.tick()
        g.run(0x4208FF, 0x420904, ecx=6 * V2["stride"], edx=w.pool, ebx=0)
        self.assertEqual([e["record"] for e in g.of_kind(DISAPPEARED)], [w.record(6)],
                         "another slot's namesake is the tribe's")
        # Renamed by the player, the stranger is still the stranger: names are
        # player-editable, so a rename alone never makes him the tribe's (Codex, #532).
        g, w = vv2()
        g.slot = 1
        w.villager(6, "Biggles", 600, 90)
        g.run(0x44C84F, 0x44C856, esi=w.record(6))
        g.run(0x41F963, 0x41F969, eax=6, esi=g.p.alloc(0x6000))
        g.tick()
        g.p.write(w.record(6) + V2["name"], b"Bigs\0")
        g.tick()
        g.run(0x4208FF, 0x420904, ecx=6 * V2["stride"], edx=w.pool, ebx=0)
        self.assertEqual(g.of_kind(DISAPPEARED), [], "a renamed stranger is still nobody's")
        # Untouched, the stranger himself is still nobody's, ticks or not.
        g, w = vv2()
        g.slot = 1
        w.villager(6, "Biggles", 600, 90)
        g.run(0x44C84F, 0x44C856, esi=w.record(6))
        g.run(0x41F963, 0x41F969, eax=6, esi=g.p.alloc(0x6000))
        g.tick()
        g.tick()
        g.run(0x4208FF, 0x420904, ecx=6 * V2["stride"], edx=w.pool, ebx=0)
        self.assertEqual(g.of_kind(DISAPPEARED), [])

    def test_the_creators_report_arrivals_and_the_save_reconciles(self):
        g, w = vv2()
        w.villager(6, "Newborn", 0, 100)
        g.run(0x44C84F, 0x44C856, esi=w.record(6))
        w.villager(7, "Twin", 0, 100)
        g.run(0x44CF04, 0x44CF0A, esi=w.record(7), ebx=0)
        self.assertEqual(g.stats()["arrived"], 2)
        for slot, ok, expected in ((3, 0, False), (0, 1, False), (3, 1, True)):
            g.saved_epilogue(0x424BF8, slot, ok)
            self.assertEqual(g.roster(slot) is not None, expected, (slot, ok))


# ---- The Secret City, The Tree of Life, New Believers --------------------------
LATER = {
    "vv3": dict(table=0x59E110, base=0x14, stride=0x1F8C, present=0xF10, health=0xE78, cause=0xE7C,
                age=0xDC4, name=0xDD4, skills=0xEAC, lookalike=0xE94, roster=0x5973F0 + 0x974,
                entry_stride=0x30, rand=0x4032D0, strings=(0x42F740, 0x42F190)),
    "vv4": dict(table=0x50E568, base=0x44, stride=0x2E3C, present=0x1CC4, health=0x1C40, cause=0x1C44,
                age=0x1B8C, name=0x1B9C, skills=None, lookalike=0x1CC7, roster=0x5025C8, entry_stride=0x5C,
                rand=0x4036D0, strings=(0x44DA20, 0x44D3D0)),
    "vv5": dict(table=0x554148, base=0x48, stride=0x2F44, present=0x1CD4, health=0x1C40, cause=0x1C44,
                age=0x1B8C, name=0x1B9C, skills=None, lookalike=0x1CE1, roster=0x5481A8, entry_stride=0x5C,
                rand=0x403660, strings=(0x450D40, 0x4506D0)),
}
EPITAPH_IDS = {}


class Later:
    def __init__(self, g: Game):
        self.g = g
        self.l = LATER[g.game]
        p = g.p
        p.stub(self.l["rand"], lambda proc: (0, 0))
        self.words = p.alloc(0x2000)
        p.stub(self.l["strings"][0], lambda proc: (proc.arg(0), 4))   # (id): the 0x20 after it is strncpy's

        def text(proc):
            at = self.words + (proc.reg("ecx") & 0x3FF) * 8
            proc.write(at, b"Ep%d\0" % (proc.reg("ecx") & 0x3FF))
            return at, 0
        p.stub(self.l["strings"][1], text)

    def record(self, i: int) -> int:
        return self.l["table"] + self.l["base"] + i * self.l["stride"]

    def villager(self, i: int, name: str, age: int, health: int, cause: int = -1) -> int:
        r = self.record(i)
        p = self.g.p
        p.write(r, bytes(self.l["stride"]))
        p.write(r + self.l["present"], b"\x01")
        p.put32(r + self.l["health"], health)
        p.put32(r + self.l["cause"], cause & 0xFFFFFFFF)
        p.put32(r + self.l["age"], age)
        p.write(r + self.l["name"], name.encode() + b"\0")
        return r

    def entry(self, slot: int) -> int:
        return self.l["roster"] + slot * self.l["entry_stride"]

    def bury(self, i: int) -> None:
        """The burial's end: the record freed, the Roster of the Dead writer
        called with it, and the hook right after the call."""
        p, g = self.g.p, self.g
        r = self.record(i)
        if g.game == "vv3":
            for k in range(16):
                p.put32(STACK + 4 * k, 0)
            p.put32(STACK + 0x34, 0xFFFFFFFF)          # nobody burying: no match in the loop
            owner = p.alloc(0x40)
            g.run(0x462293, 0x4622D2, edi=r, ebx=owner)
        else:
            owner = p.alloc(0x2000)
            village = p.alloc(0x2000)
            p.put32(owner + 0x1B80, village)
            p.put32(STACK, 0)
            start, stop = (0x46A977, 0x46A99E) if g.game == "vv4" else (0x473F8F, 0x473FB6)
            g.run(start, stop, esi=r, ebx=owner)

    def decay(self, i: int) -> None:
        g, r = self.g, self.record(i)
        if g.game == "vv3":
            clock = g.p.alloc(0x13000)
            g.p.put32(clock + 0x12F20, 1)
            g.run(0x45F437, 0x45F43D, eax=0xF0, edx=0, ecx=clock, esi=r + 0xF10)
        elif g.game == "vv4":
            g.run(0x4664B4, 0x4664BA, esi=r + 0x1CC7)
        else:
            g.run(0x46FF12, 0x46FF18, esi=r, ebx=0)

    def done(self, slot: int, typed: str) -> None:
        """The grave dialog's onEvent for Done, its box holding `typed`."""
        g, p = self.g, self.g.p
        get_text, close = {"vv3": (0x40D1E0, 0x40E020), "vv4": (0x40D420, 0x40E090),
                           "vv5": (0x40D910, 0x40E580)}[g.game]

        def text(proc):
            data = typed.encode("latin-1")[: proc.arg(1) - 1]
            proc.write(proc.arg(0), data + b"\0")
            return 0, 8
        p.stub(get_text, text)
        p.stub(close, lambda proc: (0, 0))
        dialog = p.alloc(0x100)
        p.put32(dialog + 0x50, 7)
        p.put32(dialog + 0x4C, 0x5973F0 + slot * 0x2C if g.game == "vv3" else self.entry(slot))
        p.call({"vv3": 0x41E690, "vv4": 0x41C2C0, "vv5": 0x41CB20}[g.game], [8, 7], ecx=dialog)


def later(game: str, mode: str = "stock") -> tuple[Game, Later]:
    g = Game(game, rendered(game, mode, True))
    world = Later(g)
    assert g.install() == 1
    return g, world


class LaterGames(unittest.TestCase):
    def games(self):
        for game in ("vv3", "vv4", "vv5"):
            if STOCK[game].is_file() and TEST_DLL.is_file():
                yield game

    def test_install_writes_every_site_in_every_mode_alone_and_with_everything(self):
        for game in self.games():
            install_checks(self, game)

    def test_one_wrong_byte_anywhere_installs_nothing(self):
        for game in self.games():
            one_wrong_byte_checks(self, game)

    def test_the_burial_is_a_death_record_with_the_games_grave_and_epitaph(self):
        words = {-1: "Unknown causes", 0: "Disease", 1: "Starvation", 2: "Old age", 3: "Work accident"}
        for game in self.games():
            for mode in MODES:
                g, w = later(game, mode)
                for n, cause in enumerate((2, 0, 3, -1)):
                    w.villager(n, f"Dead{n}", 600 + n, 0, cause)
                    w.bury(n)
                deaths = g.of_kind(DEATH)
                self.assertEqual([(e["record"], e["Age at death"], e["Cause of death"]) for e in deaths],
                                 [(w.record(n), str(600 + n), words[c]) for n, c in enumerate((2, 0, 3, -1))],
                                 (game, mode))
                for n, e in enumerate(deaths):
                    self.assertEqual(e["Grave"], "Untrained", (game, mode))
                    self.assertTrue(e["Epitaph"].startswith("Ep"), (game, mode, e["Epitaph"]))
                    self.assertEqual(g.p.cstring(w.entry(n)), f"Dead{n}", (game, mode))
                self.assertEqual(g.stats()["burials"], 4)

    def test_a_removed_body_is_a_death_with_no_grave(self):
        for game in self.games():
            g, w = later(game)
            w.villager(3, "Lying", 900, 0, 1)
            w.decay(3)
            w.villager(4, "Alive", 900, 50)
            w.decay(4)                      # not a body: nothing
            self.assertEqual([(e["record"], e["Cause of death"], e["Grave"]) for e in g.of_kind(DEATH)],
                             [(w.record(3), "Starvation", NO_GRAVE)], game)

    def test_an_edited_epitaph_is_an_epitaph_changed_record(self):
        for game in self.games():
            g, w = later(game)
            w.villager(0, "Elda", 1500, 0, 2)
            w.bury(0)
            old = g.of_kind(DEATH)[0]["Epitaph"]
            w.done(0, old)
            self.assertEqual(g.of_kind(EPITAPH), [], game)
            w.done(0, "Always Remembered")
            change = g.of_kind(EPITAPH)
            self.assertEqual([(e["Old epitaph"], e["New epitaph"], e["Age at death"]) for e in change],
                             [(old, "Always Remembered", "1500")], game)

    def test_spaces_typed_around_an_unchanged_epitaph_are_not_a_change(self):
        """Live, New Believers v1.35.59: Pili's grave got an "Epitaph changed"
        record reading "Respected Devotee" to "Respected Devotee   " -- three
        stray Space presses in the open box.  The game's Done copies the box
        back as it always does; the record is written only for a real edit."""
        for game in self.games():
            for mode in MODES:
                g, w = later(game, mode)
                w.villager(0, "Pili", 1188, 0, 2)
                w.bury(0)
                old = g.of_kind(DEATH)[0]["Epitaph"]
                for typed in (old + "   ", "  " + old, " " + old + " ", old):
                    w.done(0, typed)
                    self.assertEqual(g.of_kind(EPITAPH), [], (game, mode, typed))
                w.done(0, "Respected Devotee")
                self.assertEqual([(e["Old epitaph"], e["New epitaph"]) for e in g.of_kind(EPITAPH)],
                                 [(old, "Respected Devotee")], (game, mode))

    def test_the_tsunami_and_the_sealed_box_are_disappearances(self):
        if "vv3" in self.games():
            g, w = later("vv3")
            w.villager(0, "Swept", 500, 80)
            w.villager(1, "Bones", 500, 0)
            # The sweep, entered from The Tsunami's call (return 0x414B3E),
            # rand scripted to 0: every living villager is taken.
            g.p.put32(STACK, 0x414B3E)
            g.p.put32(STACK + 4, 100)
            g.p.put32(STACK + 8, 0xFFFFFFFF)
            g.p.set_reg("esp", STACK)
            g.p.set_reg("ecx", 0x59E110)
            g.p.run(0x45D990, 0x414B3E)
            gone = g.of_kind(DISAPPEARED)
            self.assertEqual([(e["record"], e["What happened"]) for e in gone],
                             [(w.record(0), "Swept away by The Tsunami")])
        if "vv4" in self.games():
            g, w = later("vv4")
            w.villager(2, "Swimmer", 500, 0)
            g.run(0x415DA6, 0x415DAD, ecx=w.record(2))
            self.assertEqual([e["What happened"] for e in g.of_kind(DISAPPEARED)],
                             ["Swept away by a wave swimming The Sealed Box back"])

    def test_the_creators_report_arrivals_and_reanimates_stand_in_is_never_the_tribes(self):
        sites = {"vv3": (0x456326, 0x456332), "vv4": (0x45F175, 0x45F181), "vv5": (0x468411, 0x46841A)}
        for game in self.games():
            g, w = later(game)
            w.villager(5, "Newborn", 0, 100)
            start, stop = sites[game]
            g.run(start, stop, esi=w.record(5), ebx=0)
            self.assertEqual(g.stats()["arrived"], 1, game)
            for slot, ok, expected in ((1, 0, False), (7, 1, False), (1, 1, True)):
                g.saved_epilogue({"vv3": 0x427D71, "vv4": 0x41F13F, "vv5": 0x4245FF}[game], slot, ok)
                self.assertEqual(g.roster(slot) is not None, expected, (game, slot, ok))
        if "vv5" in self.games():
            g, w = later("vv5")
            g.run(0x46FDE0, 0x46FDE5, ecx=0)
            w.villager(9, "Standin", 900, 0)
            g.run(0x468411, 0x46841A, esi=w.record(9))
            self.assertEqual(g.stats()["arrived"], 0)
            w.bury(9)
            self.assertEqual(g.of_kind(DEATH), [], "the stand-in's burial is not a death")

    def test_a_load_over_the_stand_ins_record_brings_a_villager_of_the_tribe(self):
        """Reanimate's stand-in is not the tribe's while it holds its record.
        New Believers ticks the companion at buildSavePath (the quit's save,
        then the load) and its load (0x46FA20) resets and refills every
        record in one call with no creator: a villager loaded into the
        stand-in's record was taken for it, and her burial was no death."""
        if "vv5" not in self.games():
            return
        for same_slot in (True, False):
            g, w = later("vv5")
            g.slot = 1
            g.run(0x46FDE0, 0x46FDE5, ecx=0)
            w.villager(9, "Standin", 900, 0)
            g.run(0x468411, 0x46841A, esi=w.record(9))
            g.p.write(w.record(9) + w.l["name"], b"Kito\0")   # 0x420015: the reanimated villager's name
            g.tick()                                          # the quit's save
            if not same_slot:
                g.slot = 2
            g.tick()                                          # the load's buildSavePath
            w.villager(9, "Kaya", 700, 0)                     # 0x46FA20 refills the record
            w.bury(9)
            self.assertEqual([e["record"] for e in g.of_kind(DEATH)], [w.record(9)], same_slot)
        # Her body left unburied to decay is a death too.
        g, w = later("vv5")
        g.slot = 1
        g.run(0x46FDE0, 0x46FDE5, ecx=0)
        w.villager(9, "Standin", 900, 0)
        g.run(0x468411, 0x46841A, esi=w.record(9))
        g.p.write(w.record(9) + w.l["name"], b"Kito\0")
        g.tick()
        w.villager(9, "Kaya", 700, 0)
        w.decay(9)
        self.assertEqual([e["record"] for e in g.of_kind(DEATH)], [w.record(9)], "decayed")
        # A new stand-in in the same record before any tick is a stand-in
        # still, though the last one's name is remembered.
        g, w = later("vv5")
        g.slot = 1
        g.run(0x46FDE0, 0x46FDE5, ecx=0)
        w.villager(9, "Standin", 900, 0)
        g.run(0x468411, 0x46841A, esi=w.record(9))
        g.p.write(w.record(9) + w.l["name"], b"Kito\0")
        g.tick()
        g.run(0x46FDE0, 0x46FDE5, ecx=0)
        w.villager(9, "Standin", 900, 0)
        g.run(0x468411, 0x46841A, esi=w.record(9))
        g.p.write(w.record(9) + w.l["name"], b"Ama\0")
        w.bury(9)
        self.assertEqual(g.of_kind(DEATH), [], "the second stand-in's burial is not a death")
        # The next save, before any tick, names her in the village's roster.
        for name, member in (("Kaya", True), ("Kito", False)):
            g, w = later("vv5")
            g.slot = 1
            g.run(0x46FDE0, 0x46FDE5, ecx=0)
            w.villager(9, "Standin", 900, 0)
            g.run(0x468411, 0x46841A, esi=w.record(9))
            g.p.write(w.record(9) + w.l["name"], b"Kito\0")
            g.tick()
            g.tick()
            if member:
                w.villager(9, name, 700, 90)                  # the load
            g.saved_epilogue(0x4245FF, 1, 1)
            self.assertEqual(name.encode() in (g.roster(1) or b""), member, name)
        # Untouched, the stand-in itself is still nobody's after ticks.
        g, w = later("vv5")
        g.slot = 1
        g.run(0x46FDE0, 0x46FDE5, ecx=0)
        w.villager(9, "Standin", 900, 0)
        g.run(0x468411, 0x46841A, esi=w.record(9))
        g.p.write(w.record(9) + w.l["name"], b"Kito\0")
        g.tick()
        g.tick()
        w.bury(9)
        self.assertEqual(g.of_kind(DEATH), [])


_RENDERS_256: dict = {}


def rendered_256(game: str, mode: str) -> bytes:
    """Every public patch of the game WITH 256 Villagers (Experimental)."""
    if (game, mode) not in _RENDERS_256:
        import vv_fun_patcher as vfp
        build = next(b for b in vfp.load_builds() if b.id == game)
        rows = [p.id for p in vfp.load_public_fun_patches() if p.game_id == game]
        assert f"{game}_population_256" in rows
        data, _ = vfp.render_patched_bytes(STOCK[game], build, mode, rows)
        _RENDERS_256[(game, mode)] = bytes(data)
    return _RENDERS_256[(game, mode)]


SEX = {"vv3": 0xDC8, "vv4": 0x1B90, "vv5": 0x1B90}


class Later256(Later):
    """The same world, with the villager table where the 256 build keeps it."""

    def record(self, i: int) -> int:
        return 0x800000 + self.l["base"] + i * self.l["stride"]


def later_256(game: str, mode: str = "stock") -> tuple[Game, Later256]:
    g = Game(game, rendered_256(game, mode))
    world = Later256(g)
    assert g.install() == 1
    return g, world


class LaterGames256(unittest.TestCase):
    """Cause of Death in the 256 Villagers (Experimental) builds: the
    companion reads the relocated table and its 256 slots from the
    executable, so deaths, removals, disappearances, arrivals and the
    Unaccounted reconciliation all reach villagers in records 150..255."""

    def games(self):
        for game in ("vv3", "vv4", "vv5"):
            if STOCK[game].is_file() and TEST_DLL.is_file():
                yield game

    def test_install_writes_every_site_in_every_mode(self):
        for game in self.games():
            for mode in MODES:
                g = Game(game, rendered_256(game, mode))
                self.assertEqual(g.install(), 1, (game, mode))
                for d in manifest(game)["runtime_detours"]:
                    self.assertEqual(g.p.read(int(d["va"], 16), 1), b"\xE9", (game, mode, d["va"]))

    def test_burials_and_a_removed_body_above_slot_150_are_death_records(self):
        words = {-1: "Unknown causes", 0: "Disease", 1: "Starvation", 2: "Old age", 3: "Work accident"}
        for game in self.games():
            for mode in MODES:
                g, w = later_256(game, mode)
                slots = (150, 200, 255)
                for n, (i, cause) in enumerate(zip(slots, (2, 0, 3))):
                    w.villager(i, f"Dead{i}", 600 + n, 0, cause)
                    w.bury(i)
                w.villager(230, "Lying", 900, 0, 1)
                w.decay(230)
                deaths = g.of_kind(DEATH)
                self.assertEqual([(e["record"], e["Cause of death"]) for e in deaths],
                                 [(w.record(i), words[c]) for i, c in zip(slots, (2, 0, 3))]
                                 + [(w.record(230), "Starvation")], (game, mode))
                self.assertEqual(deaths[-1]["Grave"], NO_GRAVE, (game, mode))
                self.assertEqual(g.stats()["burials"], 3, (game, mode))

    def test_the_tsunami_takes_villagers_above_slot_150(self):
        if "vv3" not in self.games():
            return
        g, w = later_256("vv3")
        w.villager(151, "Swept", 500, 80)
        w.villager(255, "Swept2", 500, 80)
        w.villager(200, "Bones", 500, 0)
        g.p.put32(STACK, 0x414B3E)
        g.p.put32(STACK + 4, 100)
        g.p.put32(STACK + 8, 0xFFFFFFFF)
        g.p.set_reg("esp", STACK)
        g.p.set_reg("ecx", 0x800000)
        g.p.run(0x45D990, 0x414B3E)
        self.assertEqual([(e["record"], e["What happened"]) for e in g.of_kind(DISAPPEARED)],
                         [(w.record(151), "Swept away by The Tsunami"),
                          (w.record(255), "Swept away by The Tsunami")])

    def test_arrivals_and_the_unaccounted_reconciliation_above_slot_150(self):
        sites = {"vv3": (0x456326, 0x456332), "vv4": (0x45F175, 0x45F181), "vv5": (0x468411, 0x46841A)}
        saves = {"vv3": 0x427D71, "vv4": 0x41F13F, "vv5": 0x4245FF}
        for game in self.games():
            g, w = later_256(game)
            w.villager(10, "Low", 600, 80)
            w.villager(252, "High", 600, 80)
            g.saved_epilogue(saves[game], 1, 1)               # the first roster
            self.assertEqual(g.of_kind(UNACCOUNTED), [], game)
            # a birth into record 254, reported by the game's own creator
            w.villager(254, "Newborn", 0, 100)
            start, stop = sites[game]
            g.run(start, stop, esi=w.record(254), ebx=0)
            self.assertEqual(g.stats()["arrived"], 1, game)
            # record 252 emptied and record 253 filled, neither reported
            g.p.write(w.record(252) + w.l["present"], b"\x00")
            w.villager(253, "Stranger", 600, 80)
            g.p.put32(w.record(253) + SEX[game], 1)
            g.saved_epilogue(saves[game], 1, 1)
            got = sorted((e["Record"], e["What"]) for e in g.of_kind(UNACCOUNTED))
            self.assertEqual(got, [("252", "Left the village with no Death or Disappeared record"),
                                   ("253", "Arrived with no Birth record or known arrival")], game)
            self.assertEqual(struct.unpack_from("<4I", g.roster(1))[3], 3, game)   # Low, Stranger, Newborn


PARENTAGE_DLL = ROOT / "assets" / "parentage" / "VVFP Parentage Export.dll"


class _Accepted(Exception):
    pass


class DeathRecords256(unittest.TestCase):
    """"VVFP Parentage Export.dll"'s WriteVillageRecord, which files the
    Death, Disappeared and Unaccounted records, accepts a villager's record
    from any of the table's slots as the executable states them: 150..255
    in a 256 Villagers build, refused past 149 in the ordinary one."""

    def accepted(self, game: str, exe: bytes, table: int, slot: int) -> bool:
        p = Process(exe, PARENTAGE_DLL)
        p.api_handlers["GetModuleHandleW"] = lambda proc: ((0x400000 if proc.arg(0) == 0 else 0), 4)

        def past_the_check(proc):
            raise _Accepted()
        # the first thing an accepted record does is name its session
        p.api_handlers["GetCurrentProcessId"] = past_the_check
        l = LATER[game]
        r = table + l["base"] + slot * l["stride"]
        p.write(r + l["name"], b"Someone\0")
        p.write(r + l["present"], b"\x01")
        try:
            return p.export("WriteVillageRecord", int(game[-1]), DEATH, r, 1, 0, 0, 1) == 1
        except _Accepted:
            return True

    def test_every_slot_of_the_table_the_executable_states(self):
        for game in ("vv3", "vv4", "vv5"):
            if not STOCK[game].is_file():
                continue
            big, ordinary = rendered_256(game, "stock"), rendered(game, "stock", True)
            for slot in (0, 149, 150, 200, 255):
                with self.subTest(game=game, slot=slot):
                    self.assertTrue(self.accepted(game, big, 0x800000, slot))
                    if slot <= 150:          # record 150 is the first past the ordinary table
                        self.assertEqual(self.accepted(game, ordinary, LATER[game]["table"], slot), slot < 150)


@unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
class CustomIslandEventDisappearsEveryGame(unittest.TestCase):
    """The Custom Island Event's "Disappears" is a "Disappeared in a custom
    island event" record in all five games, each in the state its own
    "Disappears" (native/vvfp_story_upgrades/story_c<N>.inc) leaves the
    record: presence cleared, and in The Tree of Life health 0 as well
    (The Sealed Box's own disappearance, which c4_vanish copies).  Before
    the fix The Tree of Life's asked for health above 0 and wrote nothing,
    so the villager surfaced later as Unaccounted."""

    def vanish(self, game: str, mode: str) -> None:
        if game == "vv1":
            g, w = vv1(mode)
            present = V1["present"]
            r = w.villager(3, "Vanisher", 640, 70)
        elif game == "vv2":
            g, w = vv2(mode)
            present = V2["present"]
            r = w.villager(3, "Vanisher", 640, 70)
        else:
            g, w = later(game, mode)
            present = LATER[game]["present"]
            r = w.villager(3, "Vanisher", 640, 70)
        no = int(game[-1])
        g.p.export("VvfpCauseVanished", no, 3)               # still here: nothing
        self.assertEqual(g.of_kind(DISAPPEARED), [], (game, mode))
        if game == "vv4":
            g.p.put32(r + LATER["vv4"]["health"], 0)          # c4_vanish: 0x46AF00(0, -1) first
        g.p.write(r + present, b"\x00")
        g.p.export("VvfpCauseVanished", no, 3)
        g.p.export("VvfpCauseVanished", no % 5 + 1, 3)       # another game: nothing
        gone = g.of_kind(DISAPPEARED)
        self.assertEqual([(e["record"], e["Age"], e["What happened"]) for e in gone],
                         [(r, "640", "Disappeared in a custom island event")], (game, mode))
        self.assertEqual(g.stats()["departed"], 1, (game, mode))

    def test_every_game_writes_the_disappeared_record(self):
        for game in NAMES:
            if not STOCK[game].is_file():
                continue
            for mode in MODES:
                self.vanish(game, mode)

    def test_a_dead_body_is_never_a_disappearance_where_the_vanish_keeps_health(self):
        for game in ("vv3", "vv5"):
            if not STOCK[game].is_file():
                continue
            g, w = later(game)
            r = w.villager(2, "Body", 700, 0, 2)
            g.p.write(r + LATER[game]["present"], b"\x00")
            g.p.export("VvfpCauseVanished", int(game[-1]), 2)
            self.assertEqual(g.of_kind(DISAPPEARED), [], game)

    def test_the_tree_of_life_vanish_writes_health_then_presence(self):
        """The record state the test above gives The Tree of Life is the one
        c4_vanish leaves (source pin: 0x46AF00 with 0, then +0x1CC4 = 0)."""
        source = (ROOT / "native" / "vvfp_story_upgrades" / "story_c4.inc").read_text(encoding="utf-8")
        body = source[source.index("static int c4_vanish(int index)"):]
        body = body[:body.index("\n}\n")]
        self.assertLess(body.index("TC2(0x46AF00u, r + 0x1C34, 0, -1);"), body.index("r[0x1CC4] = 0;"))


@unittest.skipUnless(STOCK["vv5"].is_file(), STOCK_ABSENT)
@unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
class NewBelieversLeaveForTheHeathens(unittest.TestCase):
    """The owner: a believer who goes over to the Heathens (The Mask's
    "...and is a believer no more", the Custom Island Event's "Becomes a
    Heathen") leaves the tribe -- a Disappeared record, "Left the tribe:
    became a Heathen", mirroring the Arrived "Converted from the Heathens".
    Never Unaccounted, never logged twice, and converting back still writes
    the Arrived record."""

    SAVE = 0x4245FF
    FACTION = 0x1CEC

    def test_a_believer_who_becomes_a_heathen_leaves_the_tribe_once(self):
        for mode in MODES:
            g = Game("vv5", rendered("vv5", mode, True), 1)
            w = Later(g)
            self.assertEqual(g.install(), 1)
            leaver = w.villager(4, "Leaver", 900, 80)
            w.villager(5, "Stay", 800, 80)
            heathen = w.villager(6, "Pagan", 700, 80)
            g.p.write(heathen + self.FACTION, b"\x01")         # a Heathen from the first sight: nothing
            g.tick()
            g.saved_epilogue(self.SAVE, 1, 1)                  # the roster the next save reconciles against
            g.p.write(leaver + self.FACTION, b"\x01")          # The Mask, result A / "Becomes a Heathen"
            g.tick()
            g.tick()
            gone = g.of_kind(DISAPPEARED)
            self.assertEqual([(e["record"], e["Age"], e["Sex"], e["What happened"]) for e in gone],
                             [(leaver, "900", "Male", "Left the tribe: became a Heathen")], mode)
            self.assertEqual(gone[0]["check"], 1, mode)
            self.assertEqual(g.stats()["left_tribe"], 1, mode)
            self.assertEqual(g.stats()["departed"], 0, mode)   # still a record of the roster
            g.saved_epilogue(self.SAVE, 1, 1)
            g.tick()
            self.assertEqual(g.of_kind(UNACCOUNTED), [], mode)
            self.assertEqual(len(g.of_kind(DISAPPEARED)), 1, mode)
            # Converted back: the Arrived record, as for any Heathen.
            g.p.write(leaver + self.FACTION, b"\x00")
            g.tick()
            g.saved_epilogue(self.SAVE, 1, 1)
            arrived = g.of_kind(ARRIVED)
            self.assertEqual([(e["record"], e["How"]) for e in arrived],
                             [(leaver, "Converted from the Heathens")], mode)
            self.assertEqual(g.of_kind(UNACCOUNTED), [], mode)
            self.assertEqual(len(g.of_kind(DISAPPEARED)), 1, mode)

    def test_an_arrival_not_yet_written_is_written_before_the_leaving(self):
        g = Game("vv5", rendered("vv5", "stock", True), 1)
        w = Later(g)
        self.assertEqual(g.install(), 1)
        g.tick()
        g.saved_epilogue(self.SAVE, 1, 1)
        r = w.villager(7, "Newcomer", 500, 90)
        g.run(0x468411, 0x46841A, esi=r, ebx=0)                # the creator: an arrival
        g.tick()
        g.p.write(r + self.FACTION, b"\x01")
        g.tick()
        kinds = [(e["kind"], e["record"]) for e in g.logged if e["kind"] in (ARRIVED, DISAPPEARED)]
        self.assertEqual(kinds, [(ARRIVED, r), (DISAPPEARED, r)])
        g.saved_epilogue(self.SAVE, 1, 1)
        self.assertEqual(len(g.of_kind(ARRIVED)), 1)
        self.assertEqual(g.of_kind(UNACCOUNTED), [])

    FAITH = 0x1CF0

    @staticmethod
    def converting(g: Game) -> None:
        """SetFaith 0x467F90 converts only in play: the game object's byte
        +0x17E39 (0x425950 returns the object).  0x4669E0's two leaves --
        the status text 0x44EF60 (thiscall, two arguments) and the activity
        stop 0x473440 it tail-jumps to -- are scripted; the faction setter
        between them is the game's own, detoured by the companion."""
        p = g.p
        world = p.alloc(0x18000)
        p.write(world + 0x17E39, b"\x01")
        p.stub(0x425950, lambda q: (world, 0))
        p.stub(0x44EF60, lambda q: (0, 8))
        p.stub(0x473440, lambda q: (0, 0))

    def test_faith_falling_to_0_in_the_catch_up_leaves_the_tribe_at_once(self):
        """The belief drift 0x468040 is called only by the life tick 0x472C90,
        which runs for every age unit live and in the load-time catch-up (and
        a Time Warp).  When it brings faith to 0, SetFaith 0x467F90 converts
        through 0x4669E0 and the faction setter 0x466880.  In the catch-up no
        tick comes between (the tick's first look finds a Heathen, and the
        roster keeps Heathens), so the record is written at the setter, once,
        and no later tick or save writes another or calls her Unaccounted."""
        for mode in MODES:
            g = Game("vv5", rendered("vv5", mode, True), 1)
            w = Later(g)
            self.assertEqual(g.install(), 1)
            self.converting(g)
            drifter = w.villager(4, "Drifter", 900, 80)
            w.villager(5, "Stay", 800, 80)
            g.p.put32(drifter + self.FAITH, 3)
            g.p.call(0x467F90, [0, 1], ecx=drifter)              # no tick before it: the catch-up
            self.assertEqual(g.p.read(drifter + self.FACTION, 1), b"\x01", mode)
            gone = g.of_kind(DISAPPEARED)
            self.assertEqual([(e["record"], e["Age"], e["Sex"], e["What happened"]) for e in gone],
                             [(drifter, "900", "Male", "Left the tribe: became a Heathen")], mode)
            self.assertEqual((gone[0]["check"], gone[0]["detail"]), (1, 1), mode)
            g.tick()
            g.saved_epilogue(self.SAVE, 1, 1)
            g.tick()
            g.saved_epilogue(self.SAVE, 1, 1)
            self.assertEqual(len(g.of_kind(DISAPPEARED)), 1, mode)
            self.assertEqual(g.of_kind(UNACCOUNTED), [], mode)
            self.assertEqual(g.stats()["left_tribe"], 1, mode)
            self.assertEqual(g.stats()["departed"], 0, mode)

    def test_only_the_setter_calls_that_make_a_believer_a_heathen_leave(self):
        """0x466880's seven callers in the stock executable: 0x4669E0 (return
        0x466A04), The Spa (0x415D11) and The Cracked Mask (0x416C60) make a
        believer a Heathen; the conversion to a believer (0x46697D, 0x41699F),
        a load's copy (0x466BEF) and the Heathen creator (0x46FC53) never
        do.  A Heathen set again (The Spa's own second call) is no change."""
        cases = ((0x415D11, 1, 0, True), (0x416C60, 1, 0, True), (0x466A04, 1, 0, True),
                 (0x46FC53, 1, 0, False), (0x466BEF, 1, 0, False), (0x466982, 0, 1, False),
                 (0x4169A4, 0, 1, False), (0x415D11, 1, 1, False), (0x466A04, 0, 0, False))
        for ret, value, already, leaves in cases:
            g = Game("vv5", rendered("vv5", "stock", True), 1)
            w = Later(g)
            self.assertEqual(g.install(), 1)
            r = w.villager(3, "Subject", 640, 70)
            g.p.write(r + self.FACTION, bytes([already]))
            g.p.put32(STACK, ret)
            g.p.put32(STACK + 4, value)
            g.run(0x466880, ret, ecx=r)
            self.assertEqual(g.p.read(r + self.FACTION, 1), bytes([value]), hex(ret))
            self.assertEqual([e["What happened"] for e in g.of_kind(DISAPPEARED)],
                             ["Left the tribe: became a Heathen"] if leaves else [], (hex(ret), value, already))

    def test_no_other_game_has_a_faction_to_leave_by(self):
        source = (ROOT / "native" / "vvfp_cause_of_death" / "cod_arrivals.inc").read_text(encoding="utf-8")
        tick = source[source.index("static void arrival_tick(void) {"):]
        tick = tick[:tick.index("\n}\n")]
        self.assertIn("if (REC[g_game].heathen == 0u || records == NULL) {", tick)
        self.assertLess(tick.index("REC[g_game].heathen == 0u"), tick.index("arrival_left_for_the_heathens(i, record);"))


class ManifestsAndShipping(unittest.TestCase):
    def test_rows_are_public_default_on_and_pin_the_dll(self):
        import hashlib
        import vv_fun_patcher as vfp
        public = {p.id: p for p in vfp.load_public_fun_patches()}
        sha = hashlib.sha256(SHIPPED_DLL.read_bytes()).hexdigest().upper()
        for game in NAMES:
            m = manifest(game)
            self.assertIn(f"{game}_cause_of_death", public)
            self.assertTrue(m["enabled"] and m["catalog_enabled"] and not m["catalog_hidden"])
            self.assertEqual(m["patches"], [])
            self.assertEqual(m["companion_files"][0]["sha256"], sha)
            self.assertEqual(m["dependencies"], [f"{game}_enable_origins_exclusive_features"])
            self.assertEqual(m["needs_on"][0]["id"], f"{game}_write_parentage_log")
            self.assertIn("**", m["description"])

    def test_every_origins_companion_carries_the_bridge_wherever_the_story_bridge_runs(self):
        for source in ("native/vv1_origins_icons/vv1_origins_icons.c",
                       "native/vv2_origins_icons/vv2_origins_icons.c",
                       "native/vv3_full_mastery_candidate/vv3_full_mastery_candidate.c",
                       "native/vv4_origins_icons/vv4_origins_icons.c",
                       "native/vv5_task9_origins/vv5_task9_origins.c"):
            text = (ROOT / source).read_text(encoding="utf-8")
            lines_ = text.splitlines()
            calls = [n for n, line in enumerate(lines_) if line.strip().startswith("vvfp_story_bridge(")]
            self.assertTrue(calls, source)
            for n in calls:
                self.assertTrue(lines_[n + 1].strip().startswith("vvfp_cause_bridge("), (source, n))

    def test_the_companions_tell_each_other_by_shipped_name_and_export(self):
        reset = (ROOT / "native/save_reset_export/save_reset_export.c").read_text(encoding="utf-8")
        self.assertIn('GetModuleHandleA("VVFP Cause of Death.dll")', reset)
        self.assertIn('GetProcAddress(cause, "VvfpCauseVillageReset")', reset)
        self.assertLess(reset.index("notify_cause_of_death(game, slot);"),
                        reset.index("return vv_reset_slot_state(game, slot, header);"))
        story = (ROOT / "native/vvfp_story_upgrades/story_custom.inc").read_text(encoding="utf-8")
        self.assertIn('GetModuleHandleA("VVFP Cause of Death.dll")', story)
        self.assertIn('GetProcAddress(module, "VvfpCauseVanished")', story)
        parentage = (ROOT / "native/parentage_export/parentage_export.c").read_text(encoding="utf-8")
        self.assertIn('GetProcAddress(module, "VvfpCauseNoteArrival")', parentage)
        for name in ("vvfp_cause_of_death.def", "vvfp_cause_of_death_test.def"):
            text = (ROOT / "native/vvfp_cause_of_death" / name).read_text(encoding="utf-8")
            for export in ("VvfpCauseVillageReset=_VvfpCauseVillageReset@8",
                           "VvfpCauseVanished=_VvfpCauseVanished@8",
                           "VvfpCauseNoteArrival=_VvfpCauseNoteArrival@8"):
                self.assertIn(export, text)

    def test_the_release_ships_the_dll(self):
        text = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        self.assertIn("assets/cause_of_death/VVFP Cause of Death.dll", text)


if __name__ == "__main__":
    unittest.main()
