"""Esteemed Elders' Totems Use No Villager Records (The Lost Children).

The owner (2026-10-19): a totem statue is a movable decoration, not one of the 256 villager records.
"VVFP VV2 Totems.dll" keeps every totem in a store of its own, saved per save in ElderTotems.dat.

Everything here runs the SHIPPED companion and the stock executable in an emulator
(tests/story_emulator.py): VvfpStartup installs the detours as at game start, and then the game's own
code runs through them -- the elder pass, the load and save routines, the draw loop and the Map, the
click, the name panel and the drag -- with the game's renderer, sound, particle and terrain routines
answered by stubs that record what they were asked.  The file the companion writes is parsed by
src/vv_vv2_totem_store.py, so both sides read one format.
"""
from __future__ import annotations

import hashlib
import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Lost Children.exe"
DLL = ROOT / "assets" / "vv2_totems" / "VVFP VV2 Totems.dll"
MANIFEST = ROOT / "data" / "vv2_totems_out_of_entries_feature.json"

try:
    from story_emulator import HEAP, Process  # noqa: E402
    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

import vv_vv2_totem_store as store_mod  # noqa: E402

STRIDE = 0xE48C
WORLD_GLOBAL = 0x499F24
DOCS = "C:\\Docs"
SAVE_FOLDER = DOCS + "\\LDW\\Game"


def store_file(slot: int) -> str:
    return (SAVE_FOLDER + f"\\Virtual Villagers Fun Patcher\\Save {slot}\\Data\\Elder Totems\\ElderTotems.dat")


class FakeFiles:
    """The few file APIs the companion uses, over a dict (path, case-folded -> bytes)."""

    def __init__(self, proc: "Process"):
        self.p = proc
        self.files: dict[str, bytes] = {}
        self.handles: dict[int, list] = {}
        self.next = 0x100
        self.locked: set[str] = set()
        self.last_error = 2
        self.heap: dict[int, int] = {}
        for name in ("SHGetSpecialFolderPathA", "GetModuleFileNameA", "CreateDirectoryA", "CreateDirectoryW",
                     "GetFileAttributesA", "GetFileAttributesExA", "CreateFileA", "ReadFile", "WriteFile",
                     "FlushFileBuffers", "CloseHandle", "MoveFileExA", "DeleteFileA", "GetLastError",
                     "GetProcessHeap", "HeapAlloc", "HeapReAlloc", "HeapFree", "lstrcpynA", "GetTickCount",
                     "VirtualAlloc", "VirtualFree", "MultiByteToWideChar", "GetFileSize"):
            proc.api_handlers[name] = getattr(self, name)

    def GetFileSize(self, p):
        return len(self.files[self.handles[p.arg(0)][0]]), 8

    def MultiByteToWideChar(self, p):
        text = p.cstring(p.arg(2)) if p.arg(3) == 0xFFFFFFFF else p.read(p.arg(2), p.arg(3)).decode("latin-1")
        wide = text.encode("utf-16-le") + (b"\0\0" if p.arg(3) == 0xFFFFFFFF else b"")
        if p.arg(5):
            p.write(p.arg(4), wide[: 2 * p.arg(5)])
        return len(wide) // 2, 24

    def VirtualAlloc(self, p):
        return p.alloc(p.arg(1)), 16

    def VirtualFree(self, p):
        return 1, 12

    @staticmethod
    def key(path: str) -> str:
        return path.lower()

    def SHGetSpecialFolderPathA(self, p):
        p.write(p.arg(1), DOCS.encode() + b"\0")
        return 1, 16

    def GetModuleFileNameA(self, p):
        path = b"C:\\Games\\Village\\Game.exe"
        p.write(p.arg(1), path + b"\0")
        return len(path), 12

    def CreateDirectoryA(self, p):
        return 1, 8

    def CreateDirectoryW(self, p):
        return 1, 8

    def GetFileAttributesA(self, p):
        return (0x80 if self.key(p.cstring(p.arg(0))) in self.files else 0xFFFFFFFF), 4

    def GetFileAttributesExA(self, p):
        name = self.key(p.cstring(p.arg(0)))
        if name not in self.files:
            self.last_error = 2
            return 0, 12
        size = len(self.files[name])
        p.write(p.arg(2), struct.pack("<I", 0x80) + bytes(24) + struct.pack("<II", 0, size))
        return 1, 12

    def CreateFileA(self, p):
        name = self.key(p.cstring(p.arg(0)))
        access, disposition = p.arg(1), p.arg(4)
        if name in self.locked:
            self.last_error = 32                        # ERROR_SHARING_VIOLATION
            return 0xFFFFFFFF, 28
        if disposition == 3 and name not in self.files:  # OPEN_EXISTING
            self.last_error = 2
            return 0xFFFFFFFF, 28
        if access & 0x40000000:                         # GENERIC_WRITE
            self.files[name] = b""
        handle = self.next
        self.next += 4
        self.handles[handle] = [name, 0]
        return handle, 28

    def ReadFile(self, p):
        name, pos = self.handles[p.arg(0)]
        data = self.files[name][pos:pos + p.arg(2)]
        p.write(p.arg(1), data)
        p.put32(p.arg(3), len(data))
        self.handles[p.arg(0)][1] = pos + len(data)
        return 1, 20

    def WriteFile(self, p):
        name = self.handles[p.arg(0)][0]
        self.files[name] += p.read(p.arg(1), p.arg(2))
        p.put32(p.arg(3), p.arg(2))
        return 1, 20

    def FlushFileBuffers(self, p):
        return 1, 4

    def CloseHandle(self, p):
        self.handles.pop(p.arg(0), None)
        return 1, 4

    def MoveFileExA(self, p):
        src, dst, flags = self.key(p.cstring(p.arg(0))), self.key(p.cstring(p.arg(1))), p.arg(2)
        if src not in self.files:
            self.last_error = 2
            return 0, 12
        if dst in self.files and not flags & 1:
            self.last_error = 183
            return 0, 12
        self.files[dst] = self.files.pop(src)
        return 1, 12

    def DeleteFileA(self, p):
        return (1 if self.files.pop(self.key(p.cstring(p.arg(0))), None) is not None else 0), 4

    def GetLastError(self, p):
        return self.last_error, 0

    def GetProcessHeap(self, p):
        return 0x1234, 0

    def HeapAlloc(self, p):
        size = p.arg(2)
        at = p.alloc(size)
        self.heap[at] = size
        return at, 12

    def HeapReAlloc(self, p):
        old, size = p.arg(2), p.arg(3)
        at = p.alloc(size)
        p.write(at, p.read(old, min(size, self.heap.get(old, 0))))
        self.heap[at] = size
        return at, 16

    def HeapFree(self, p):
        return 1, 12

    def lstrcpynA(self, p):
        out, source, size = p.arg(0), p.arg(1), p.arg(2)
        raw = p.cstring(source).encode("latin-1")[: max(size - 1, 0)]
        if size > 0:
            p.write(out, raw + b"\0")
        return out, 12

    def GetTickCount(self, p):
        return 1000, 0


def emulated(cls):
    return unittest.skipUnless(HAVE_EMULATOR, "capstone/unicorn/pefile not installed")(
        unittest.skipUnless(STOCK.is_file(), "the stock executable is not in research/stock-executables")(
            unittest.skipUnless(DLL.is_file(), "the companion is not built")(cls)))


class Village:
    """A stock Lost Children process with the companion installed and a world of 256 records."""

    def __init__(self):
        self.p = Process(STOCK.read_bytes(), DLL)
        self.fs = FakeFiles(self.p)
        self.world = self.p.alloc(0xE57600)
        self.game = self.p.alloc(0x31000)
        self.p.put32(WORLD_GLOBAL, self.world)
        self.p.put32(self.world + 0xE574D4, self.game)
        self.p.put32(self.game + 0x305A4, self.world)
        self.p.put32(self.game + 0x304F0, 0xFFFFFFFF)
        for k in range(256):
            self.p.put32(self.world + 0xE57090 + 4 * k, k)
        self.calls: list[tuple[str, tuple]] = []
        self.clock = 5000
        self.rolls = 0
        self._stubs()
        self.p.export("VvfpStartup", 2, 0)

    def _record(self, name, pop, count):
        def fn(p):
            self.calls.append((name, tuple(p.arg(i) for i in range(count))))
            return 0, pop
        return fn

    def _stubs(self):
        p = self.p
        p.stub(0x403200, lambda q: (self.clock, 0))                  # the game clock
        p.stub(0x4257A0, self._record("message", 8, 2))
        p.stub(0x4095A0, self._record("shadow", 0xC, 3))
        p.stub(0x4095C0, self._record("frame", 0x10, 4))
        p.stub(0x409600, self._record("draw6", 0x18, 6))
        p.stub(0x409610, self._record("map", 0x18, 6))
        p.stub(0x4181D0, lambda q: (self.terrain, 8))
        p.stub(0x4239D0, self._record("particles", 0x1C, 7))
        p.stub(0x423980, self._record("sparkles", 0xC, 3))
        p.stub(0x43F010, self._record("sound", 4, 1))
        p.stub(0x43F030, self._record("sound_at", 8, 2))
        p.stub(0x41C1D0, self._record("puzzle", 0, 0))
        p.stub(0x4031A0, lambda q: (0, 0))                           # rand() -> 0
        for va in (0x40A150, 0x40A140):                             # the cursor's size (mouse handler)
            p.stub(va, lambda q: (0, 0))
        p.stub(0x4084D0, lambda q: (0, 0xC))
        p.stub(0x401FF0, lambda q: (self.world, 0))
        p.stub(0x401E60, lambda q: (0, 0))
        p.stub(0x401E50, lambda q: (0, 0))

    terrain = 0

    def rec(self, i: int) -> int:
        return self.world + i * STRIDE

    def villager(self, i, name, *, health=60, totem=0, x=500, y=600, head=3, body=4, sex=1, elder=0,
                 skills=(0, 0, 0, 0, 0), ttype=11, lineage=7):
        r = self.rec(i)
        p = self.p
        p.write(r + 0x30, b"\x01")
        p.put32(r + 0x04, x)
        p.put32(r + 0x08, y)
        p.put32(r + 0x52C, health)
        p.put32(r + 0x530, 300)
        p.put32(r + 0x538, sex)
        p.put32(r + 0x548, head)
        p.put32(r + 0x54C, body)
        p.put32(r + 0x550, ttype)
        p.put32(r + 0x554, lineage)
        p.write(r + 0x558, bytes([totem]))
        p.put32(r + 0x55C, x)
        p.put32(r + 0x560, y)
        p.write(r + 0x564, name.encode() + b"\0")
        p.write(r + 0x57D, b"Dad\0")
        p.write(r + 0x596, b"Mum\0")
        for k, s in enumerate(skills):
            p.put32(r + 0x7E4 + 4 * k, s)
        p.write(r + 0x7FC, bytes([elder]))

    def byte(self, i, off):
        return self.p.read(self.rec(i) + off, 1)[0]

    def i32(self, va):
        return struct.unpack("<i", self.p.read(va, 4))[0]

    def count(self) -> int:
        return self.p.export("VvfpTotemCount")

    def elder_pass(self):
        self.p.call(0x44D4C0, [], ecx=self.world)

    def load(self, slot=1):
        self.p.stub(0x4249A5, lambda q: (1, 4))                     # the game's own read succeeded
        return self.p.call(0x4249A0, [slot], ecx=self.game) & 0xFF

    def save(self, slot=1):
        self.saved = []

        def write(q):
            # The trampoline ran the routine's own push esi; push edi: drop them, then return.
            q.set_reg("esp", q.reg("esp") + 8)
            self.saved.append(q.arg(0))
            return 1, 4
        self.p.stub(0x424BA6, write)
        return self.p.call(0x424BA0, [slot], ecx=self.game) & 0xFF


@emulated
class InstallTests(unittest.TestCase):
    SITES = (0x4249A0, 0x424BA0, 0x424C80, 0x44D190, 0x44D4D1, 0x44D54C, 0x445C1C, 0x4478CD, 0x4490BB,
             0x431071, 0x431076, 0x4308D0, 0x429A83, 0x44D4C0)

    def test_every_site_is_rewritten_and_nothing_else(self):
        stock = Process(STOCK.read_bytes(), DLL)
        before = stock.read(0x401000, 0x70000)
        v = Village()
        after = v.p.read(0x401000, 0x70000)
        changed = {0x401000 + i for i in range(len(before)) if before[i] != after[i]}
        allowed = set()
        lengths = (5, 6, 7, 5, 9, 5, 9, 13, 5, 5, 9, 7, 5, 9)
        for va, n in zip(self.SITES, lengths, strict=True):
            allowed |= set(range(va, va + n))
            self.assertIn(v.p.read(va, 1)[0], (0xE8, 0xE9), hex(va))
        self.assertTrue(changed)
        self.assertLessEqual(changed, allowed)

    def test_a_site_not_stock_installs_nothing(self):
        data = bytearray(STOCK.read_bytes())
        import pefile
        pe = pefile.PE(data=bytes(data))
        off = pe.get_offset_from_rva(0x4478CD - 0x400000)
        data[off] = 0x90
        p = Process(bytes(data), DLL)
        before = p.read(0x401000, 0x70000)
        p.export("VvfpStartup", 2, 0)
        self.assertEqual(p.read(0x401000, 0x70000), before)
        self.assertEqual(p.export("VvfpTotemsActive"), 0)

    def test_other_games_install_nothing(self):
        p = Process(STOCK.read_bytes(), DLL)
        before = p.read(0x401000, 0x70000)
        p.export("VvfpStartup", 3, 0)
        self.assertEqual(p.read(0x401000, 0x70000), before)


@emulated
class CreationTests(unittest.TestCase):
    def test_a_new_elders_totem_goes_into_the_store_not_a_record(self):
        v = Village()
        v.villager(4, "Kona", skills=(90, 90, 90, 0, 0), x=400, y=500, ttype=42)
        v.elder_pass()
        self.assertEqual(v.count(), 1)
        in_use = [i for i in range(256) if v.byte(i, 0x30)]
        self.assertEqual(in_use, [4])                        # no record was taken
        self.assertEqual(v.byte(4, 0x7FC), 1)                # the elder is made
        self.assertEqual(v.i32(v.game + 0x2E514), 1)         # and counted by the game's own pass
        self.assertTrue(all(v.byte(i, 0x558) == 0 for i in range(256)))

    def test_the_first_elder_message_is_the_games_own(self):
        v = Village()
        v.p.write(v.game + 0x1FF, b"\x01")                    # the game's "not yet shown" flag
        v.villager(4, "Kona", skills=(90, 90, 90, 0, 0))
        v.elder_pass()
        self.assertIn(("message", (0x1CE, 1)), v.calls)
        self.assertEqual(v.p.read(v.game + 0x1FF, 1)[0], 0)
        self.assertEqual(v.p.read(v.game + 0x2E778, 1)[0], 1)  # the first elder's time, once

    def test_a_full_village_still_makes_the_elder_and_the_totem(self):
        v = Village()
        for i in range(256):
            v.villager(i, f"V{i}", skills=(90, 90, 90, 0, 0) if i == 9 else (0,) * 5)
        v.elder_pass()
        self.assertEqual(v.count(), 1)
        self.assertEqual(v.byte(9, 0x7FC), 1)
        self.assertEqual(sum(v.byte(i, 0x30) for i in range(256)), 256)
        self.assertTrue(all(v.byte(i, 0x558) == 0 for i in range(256)))

    def test_no_cap_on_elder_totems(self):
        v = Village()
        for i in range(60):
            v.villager(i, f"E{i}", skills=(90, 90, 90, 0, 0))
        v.elder_pass()
        self.assertEqual(v.count(), 60)                      # the stock pass stops at 50
        self.assertEqual(v.i32(v.game + 0x2E514), 60)

    def test_the_count_ignores_the_store_and_record_totems_still_count(self):
        v = Village()
        v.villager(1, "Old", health=0, totem=1)
        self.assertEqual(v.p.call(0x4259B0, [], ecx=v.game), 1)


@emulated
class LoadAndSaveTests(unittest.TestCase):
    def test_load_moves_statues_out_and_never_a_living_villager(self):
        v = Village()
        v.villager(0, "Alive", health=50)
        v.villager(1, "Statue A", health=0, totem=1, x=700, y=800, ttype=17)
        v.villager(2, "Body", health=0)
        v.villager(3, "Alive Marked", health=40, totem=1)
        v.villager(5, "Statue B", health=-3, totem=1, x=900, y=820, ttype=3)
        self.assertEqual(v.load(1), 1)
        self.assertEqual(v.count(), 2)
        self.assertEqual([i for i in range(256) if v.byte(i, 0x30)], [0, 2, 3])
        self.assertEqual(v.byte(3, 0x558), 1)                # the living one is left exactly as it was
        self.assertEqual(v.byte(1, 0x558), 0)

    def test_save_writes_the_file_and_a_new_load_reads_it_back(self):
        v = Village()
        v.villager(0, "Alive", health=50)
        v.villager(1, "Statue A", health=0, totem=1, x=700, y=800, ttype=17)
        v.load(1)
        self.assertEqual(v.save(1), 1)
        self.assertEqual(v.saved, [1])
        data = v.fs.files[store_file(1).lower()]
        parsed = store_mod.parse(data)
        self.assertEqual([t.name for t in parsed.totems], ["Statue A"])
        self.assertEqual((parsed.totems[0].x, parsed.totems[0].y, parsed.totems[0].type), (700, 800, 17))
        self.assertEqual(parsed.roster, [("Alive", 3, 4, 1)])
        # A fresh process reads it back: the save holds no statue now.
        w = Village()
        w.fs.files = dict(v.fs.files)
        w.villager(0, "Alive", health=50)
        w.load(1)
        self.assertEqual(w.count(), 1)

    def test_a_statue_already_in_the_file_is_not_doubled(self):
        v = Village()
        v.villager(0, "Alive", health=50)
        v.villager(1, "Statue A", health=0, totem=1, x=700, y=800)
        v.load(1)
        v.save(1)
        w = Village()                                        # the save restored from a backup
        w.fs.files = dict(v.fs.files)
        w.villager(0, "Alive", health=50)
        w.villager(1, "Statue A", health=0, totem=1, x=10, y=20)
        w.load(1)
        self.assertEqual(w.count(), 1)
        self.assertEqual(w.byte(1, 0x30), 0)

    def test_another_villages_file_is_set_aside_not_used(self):
        v = Village()
        v.villager(0, "Alive", health=50)
        v.villager(1, "Statue A", health=0, totem=1)
        v.load(1)
        v.save(1)
        w = Village()
        w.fs.files = dict(v.fs.files)
        w.villager(0, "Stranger", health=50)
        w.load(1)
        self.assertEqual(w.count(), 0)
        self.assertNotIn(store_file(1).lower(), w.fs.files)
        self.assertTrue(any(".another-village-" in k for k in w.fs.files))

    def test_a_village_with_only_its_statues_left_keeps_them(self):
        """Codex #598: with no villager left the roster is empty; the file is still this village's."""
        v = Village()
        v.p.write(v.game + 0x10, b"Kalahuna\0")                    # the tribe's name, as the game keeps it
        v.villager(1, "Statue A", health=0, totem=1, x=700, y=800)
        v.load(1)
        self.assertEqual(v.count(), 1)
        for _round in range(2):                                     # save -> load -> save -> load
            self.assertEqual(v.save(1), 1)
            w = Village()
            w.fs.files = dict(v.fs.files)
            w.p.write(w.game + 0x10, b"Kalahuna\0")
            w.load(1)
            self.assertEqual(w.count(), 1)
            self.assertFalse(any(".another-village-" in k for k in w.fs.files))
            v = w
        other = Village()                                           # another tribe with no villager: not its
        other.fs.files = dict(v.fs.files)
        other.p.write(other.game + 0x10, b"Elsewhere\0")
        other.load(1)
        self.assertEqual(other.count(), 0)
        self.assertTrue(any(".another-village-" in k for k in other.fs.files))

    def test_a_locked_file_leaves_the_session_stock(self):
        v = Village()
        v.fs.files[store_file(1).lower()] = b"x"
        v.fs.locked.add(store_file(1).lower())
        v.villager(1, "Statue A", health=0, totem=1)
        v.load(1)
        self.assertEqual(v.p.export("VvfpTotemsActive"), 0)
        self.assertEqual(v.byte(1, 0x30), 1)                 # nothing moved
        for i in range(2, 52):
            v.villager(i, f"S{i}", health=0, totem=1)
        v.villager(60, "Would Be Elder", skills=(90, 90, 90, 0, 0))
        v.elder_pass()                                       # 51 record totems: the game's own cap stands
        self.assertEqual(v.byte(60, 0x7FC), 0)
        self.assertEqual(v.count(), 0)

    def test_a_save_that_cannot_write_its_totems_is_refused(self):
        v = Village()
        v.villager(0, "Alive", health=50)
        v.villager(1, "Statue A", health=0, totem=1)
        v.load(1)
        v.fs.locked.add((store_file(1) + ".tmp").lower())
        self.assertEqual(v.save(1), 0)
        self.assertEqual(v.saved, [])

    def test_a_new_village_moves_an_older_file_aside_before_writing(self):
        v = Village()
        v.fs.files[store_file(2).lower()] = b"older"
        v.villager(0, "Alive", health=50)
        def reset(q):
            q.set_reg("esp", q.reg("esp") + 20)              # the routine's own five pushes
            return 0, 4
        v.p.stub(0x424C87, reset)
        v.p.call(0x424C80, [0], ecx=v.game)                  # a new tribe
        v.save(2)
        self.assertTrue(any(".replaced-" in k for k in v.fs.files))
        store_mod.parse(v.fs.files[store_file(2).lower()])


@emulated
class DrawTests(unittest.TestCase):
    def setUp(self):
        self.v = v = Village()
        v.villager(0, "Front", health=0, totem=1, x=100, y=700, ttype=2)    # record totems: key y + 0x23
        v.villager(1, "Back", health=0, totem=1, x=100, y=300, ttype=1)
        v.p.put32(v.world + 0xE57090, 1)
        v.p.put32(v.world + 0xE57094, 0)
        for k in range(2, 256):
            v.p.put32(v.world + 0xE57090 + 4 * k, k)
        # The load moves all three statues into the store; then two record totems stand again (as the
        # game itself keeps them without the store) to show the store's totems sort among records.
        v.villager(7, "Middle", health=0, totem=1, x=300, y=500, ttype=5)
        v.load(1)
        v.villager(0, "Front", health=0, totem=1, x=100, y=700, ttype=2)
        v.villager(1, "Back", health=0, totem=1, x=100, y=300, ttype=1)
        v.calls.clear()

    def frames(self):
        return [args[3] for name, args in self.v.calls if name == "frame"]

    def test_store_totems_are_drawn_in_y_order_among_the_records(self):
        v = self.v
        v.p.set_reg("esi", v.world)
        v.p.mu.emu_start(0x445C1C, 0x4478DA, count=5_000_000)
        # Store: Back (y 300, face 1), Middle (y 500, face 5), Front (y 700, face 2); records Back, Front.
        self.assertEqual(self.frames(), [1, 1, 5, 2, 2])
        shadows = [args for name, args in v.calls if name == "shadow"]
        self.assertEqual(len(shadows), 5)

    def test_store_totems_are_drawn_on_the_map(self):
        v = self.v
        v.p.call(0x4478E0, [], ecx=v.world)
        maps = sorted(args[1:4] for name, args in v.calls if name == "map")
        self.assertIn((300 // 4 + 0xAF, (500 - 0x41) // 4 + 0x29, 5), maps)


@emulated
class ClickAndDragTests(unittest.TestCase):
    def setUp(self):
        self.v = v = Village()
        v.villager(0, "Alive", health=50, x=1000, y=1000)
        v.villager(1, "Tiki", health=0, totem=1, x=300, y=400, ttype=13)
        v.load(1)
        self.ui = v.p.alloc(0x400)
        p = v.p
        p.put32(self.ui + 0x10, v.game)
        p.put32(self.ui + 0x20, v.world)
        for off in (0x08, 0x14, 0x18, 0x24, 0x244, 0x248):
            p.put32(self.ui + off, v.p.alloc(0x100))
        p.put32(self.ui + 0x1E4, 0xFFFFFFFF)
        p.put32(self.ui + 0x1E8, 0)
        p.put32(self.ui + 0x1EC, 0)
        p.put32(self.ui + 0x1F0, 800)
        p.put32(self.ui + 0x1F4, 600)
        p.put32(v.game + 0x8, 0)
        p.put32(v.game + 0xC, 0)
        v.terrain = 0                                        # open ground: a totem stands on it

    def mouse(self, event, x, y):
        return self.v.p.call(0x4308D0, [event, x, y], ecx=self.ui) & 0xFF

    def test_a_click_picks_the_store_totem_and_the_panel_names_it(self):
        v = self.v
        self.mouse(2, 310, 420)
        self.assertEqual(v.i32(v.game + 0x304F0), -1)
        self.assertEqual(v.p.read(self.ui + 0x1E0, 1)[0], 0)  # no camera drag
        v.p.set_reg("esp", 0x0FE80000)
        v.p.mu.emu_start(0x429A83, 0x429B31, count=100)
        label = v.p.cstring(v.p.u32(v.p.reg("esp")))
        self.assertEqual(label, "Tiki`s totem")

    def test_dragging_moves_the_totem_and_stores_its_home(self):
        v = self.v
        self.mouse(2, 310, 420)
        self.assertEqual(self.mouse(1, 312, 421), 1)          # under 5 pixels: not picked up yet
        self.assertEqual(self.mouse(1, 410, 450), 1)
        self.mouse(3, 410, 450)
        totems = store_mod.parse(self._saved())
        t = totems.totems[0]
        # 0x449220: camera + (mouse x - 5) - 0x14, camera + (mouse y + 0xD) - 0x20
        self.assertEqual((t.x, t.y), (410 - 5 - 0x14, 450 + 0xD - 0x20))
        self.assertIn("particles", [n for n, _a in v.calls])

    def test_ground_a_totem_cannot_stand_on_nudges_it(self):
        v = self.v
        self.mouse(2, 310, 420)
        self.mouse(1, 410, 450)
        seen = {"n": 0}

        def terrain(q):
            seen["n"] += 1
            return (0x10 if seen["n"] < 6 else 0), 8
        v.p.stub(0x4181D0, terrain)
        self.mouse(3, 410, 450)
        t = store_mod.parse(self._saved()).totems[0]
        self.assertNotEqual((t.x, t.y), (410 - 5 - 0x14, 450 + 0xD - 0x20))

    def test_a_click_beside_the_totem_selects_nothing_of_it(self):
        v = self.v
        self.mouse(2, 310, 420)
        # The hit test at the click (0x431071), now away from the totem: nothing of it is picked.
        v.p.stub(0x431076, lambda q: (q.reg("eax"), 0))    # stop right after the call, with its answer
        top = 0x0FE80000                                     # as at the call: x, y pushed by the caller
        v.p.put32(top, 0x0D000000)
        v.p.put32(top - 4, 10)
        v.p.put32(top - 8, 10)
        v.p.set_reg("esp", top - 8)
        v.p.set_reg("ecx", v.world)
        v.p.run(0x431071, 0x0D000000)
        r = v.p.reg("eax")
        del v.p.stubs[0x431076]
        self.assertEqual(r, 0xFFFFFFFF)
        v.p.set_reg("esp", 0x0FE80000)
        v.p.mu.emu_start(0x429A83, 0x429B31, count=100)
        self.assertEqual(v.p.u32(v.p.reg("esp")), 0x47443C)

    def _saved(self) -> bytes:
        self.v.save(1)
        return self.v.fs.files[store_file(1).lower()]


def folder_file(slot: int, leaf: str) -> str:
    return store_file(slot).rsplit("\\", 1)[0] + "\\" + leaf


def settings(v: "Village", on: bool, slot: int = 1) -> None:
    v.fs.files[folder_file(slot, "Elder Totem Settings.dat").lower()] = (
        f"VVFP VV2 ELDER TOTEM SETTINGS v1\nauto_give\t{1 if on else 0}\n").encode()


def pending(v: "Village", rows, renames=(), roster=(("Alive", 3, 4, 1),), slot: int = 1) -> str:
    key = folder_file(slot, "PendingElderTotems.dat").lower()
    v.fs.files[key] = store_mod.serialize_pending(slot, list(roster), list(rows), list(renames))
    return key


@emulated
class GivenAutomaticallyTests(unittest.TestCase):
    """The owner (2026-10-20): missing elder totems appear in the running game, without a repair."""

    def elder(self, v, i, name, **kw):
        v.villager(i, name, elder=1, **kw)

    def test_a_living_elder_without_a_totem_gets_one_at_load(self):
        v = Village()
        settings(v, True)
        v.villager(0, "Alive", health=50)
        self.elder(v, 3, "Old Kona", head=9, body=9, ttype=21, x=500, y=600)
        v.load(1)
        self.assertEqual(v.count(), 1)
        self.assertEqual(v.p.export("VvfpTotemFaceOf", v.rec(3)), 21 % 8)
        self.assertEqual([i for i in range(256) if v.byte(i, 0x30)], [0, 3])     # no record used

    def test_after_the_elder_pass_and_never_twice(self):
        v = Village()
        settings(v, True)
        v.villager(0, "Alive", health=50)
        v.load(1)
        self.assertEqual(v.count(), 0)
        self.elder(v, 5, "Late Elder", head=2, body=7)             # an elder without a totem, in play
        v.elder_pass()
        self.assertEqual(v.count(), 1)
        v.elder_pass()
        self.assertEqual(v.count(), 1)

    def test_an_elder_who_has_a_totem_gets_no_second(self):
        v = Village()
        settings(v, True)
        v.villager(0, "Alive", health=50)
        self.elder(v, 2, "Hoto", head=4, body=5)
        v.villager(6, "Hoto", health=0, totem=1, head=4, body=5)   # the statue, moved in at load
        v.load(1)
        self.assertEqual(v.count(), 1)

    def test_a_renamed_elder_is_matched_by_the_recorded_rename(self):
        v = Village()
        settings(v, True)
        v.villager(0, "Alive", health=50)
        self.elder(v, 2, "Hoto Kenobi", head=4, body=5)
        v.villager(6, "Hoto", health=0, totem=1, head=4, body=5)
        pending(v, [], renames=[("Hoto", "Hoto Kenobi", 4, 5)],
                roster=[("Alive", 3, 4, 1), ("Hoto Kenobi", 4, 5, 1)])
        v.load(1)
        self.assertEqual(v.count(), 1)

    def test_an_unsure_match_makes_nothing(self):
        v = Village()
        settings(v, True)
        v.villager(0, "Alive", health=50)
        self.elder(v, 2, "Hoto Kenobi", head=4, body=5)
        v.villager(6, "Hoto", health=0, totem=1, head=4, body=5)   # same looks, another name, no rename
        v.load(1)
        self.assertEqual(v.count(), 1)

    def test_a_pending_elder_who_passed_away_gets_a_totem_and_leaves_the_list_after_the_save(self):
        v = Village()
        settings(v, True)
        v.villager(0, "Alive", health=50)
        key = pending(v, [("Nina Jumapili", 2, 10, 21, 1400), ("Unsure", 1, 3, 3, 900)])
        v.villager(7, "Unsure Twin", health=0, totem=1, head=3, body=3, sex=1)
        v.load(1)
        self.assertEqual(v.count(), 2)                              # the statue, and Nina's new totem
        listed = lambda files: [row[0] for row in store_mod.parse_pending(files[key])[2]]  # noqa: E731
        # Codex #598: until ElderTotems.dat is written, Nina stays listed -- a crash now loses nothing.
        self.assertEqual(listed(v.fs.files), ["Nina Jumapili", "Unsure"])
        crashed = Village()                                         # the game closed with no save
        crashed.fs.files = dict(v.fs.files)
        settings(crashed, True)
        crashed.villager(0, "Alive", health=50)
        crashed.villager(7, "Unsure Twin", health=0, totem=1, head=3, body=3, sex=1)
        crashed.load(1)
        self.assertEqual(crashed.count(), 2)                        # given again, once
        v.save(1)
        self.assertEqual(listed(v.fs.files), ["Unsure"])           # the unsure one stays for Repair
        names = [t.name for t in store_mod.parse(v.fs.files[store_file(1).lower()]).totems]
        self.assertEqual(names.count("Nina Jumapili"), 1)
        w = Village()                                               # the next load: nothing twice
        w.fs.files = dict(v.fs.files)
        w.villager(0, "Alive", health=50)
        w.load(1)
        self.assertEqual(w.count(), 2)

    def test_nothing_with_the_setting_off(self):
        v = Village()
        settings(v, False)
        v.villager(0, "Alive", health=50)
        self.elder(v, 3, "Old Kona")
        key = pending(v, [("Nina Jumapili", 2, 10, 21, 1400)])
        before = v.fs.files[key]
        v.load(1)
        v.elder_pass()
        self.assertEqual(v.count(), 0)
        self.assertEqual(v.fs.files[key], before)

    def test_nothing_during_a_save(self):
        v = Village()
        settings(v, True)
        v.villager(0, "Alive", health=50)
        v.load(1)
        self.elder(v, 4, "Saved Elder")
        v.save(1)
        self.assertEqual(v.count(), 0)
        self.assertEqual(store_mod.parse(v.fs.files[store_file(1).lower()]).totems, [])


@emulated
class ExportTests(unittest.TestCase):
    def test_face_of_and_set_face_find_the_elders_totem(self):
        v = Village()
        v.villager(4, "Kona", skills=(90, 90, 90, 0, 0), ttype=42)
        v.elder_pass()
        self.assertEqual(v.p.export("VvfpTotemFaceOf", v.rec(4)), 42 % 8)
        self.assertEqual(v.p.export("VvfpTotemSetFace", v.rec(4), 6), 1)
        self.assertEqual(v.p.export("VvfpTotemFaceOf", v.rec(4)), 6)
        self.assertEqual(v.p.export("VvfpTotemFaceOf", v.rec(5)), 0xFFFFFFFF)


class ManifestTests(unittest.TestCase):
    def test_the_manifest_pins_the_shipped_dll(self):
        row = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(row["game_id"], "vv2")
        files = {f["destination"]: f["sha256"] for f in row["companion_files"]}
        self.assertIn("VVFP VV2 Totems.dll", files)
        if DLL.is_file():
            self.assertEqual(files["VVFP VV2 Totems.dll"], hashlib.sha256(DLL.read_bytes()).hexdigest().upper())
        self.assertEqual(row["patches"], [])

    def test_the_startup_loader_starts_the_companion(self):
        import re

        import vv_fun_patcher as vfp
        self.assertEqual(vfp.STARTUP_LOADER_COMPANIONS[21], "VVFP VV2 Totems.dll")
        header = (ROOT / "native" / "shared" / "startup_companions.h").read_text(encoding="utf-8")
        body = header[header.index("VVFP_STARTUP_COMPANIONS[] = {"):]
        body = body[:body.index("};")]
        self.assertEqual(re.findall(r'"([^"]+)"', body), list(vfp.STARTUP_LOADER_COMPANIONS))


if __name__ == "__main__":
    unittest.main()
