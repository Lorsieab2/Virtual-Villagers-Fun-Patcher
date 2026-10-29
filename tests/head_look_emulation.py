"""The emulated game for tests/test_head_look.py: an executable (stock, or as the patcher renders it) with
"VVFP Head Look.dll" installed in tests/story_emulator.py, a village in the game's own record table, the
game's save slot, and a small disk in memory for the DLL's per-save file -- so the draws and the file are
the DLL's own code end to end."""
from __future__ import annotations

import struct
from pathlib import Path

from story_emulator import STACK_TOP, Process

ROOT = Path(__file__).resolve().parents[1]
DLL = ROOT / "assets" / "head_look" / "VVFP Head Look.dll"
DOCS = "C:\\Docs"
INVALID = 0xFFFFFFFF
ERROR_FILE_NOT_FOUND, ERROR_PATH_NOT_FOUND, ERROR_ALREADY_EXISTS = 2, 3, 183


class Disk:
    """Files and folders the DLL reads and writes, by lower-cased path."""

    def __init__(self, p: Process):
        self.p = p
        self.files: dict[str, bytes] = {}
        self.folders: set[str] = {DOCS.lower()}
        self.handles: dict[int, list] = {}
        self.error = 0
        h = p.api_handlers
        h.update(
            SHGetSpecialFolderPathW=self._docs_w, SHGetSpecialFolderPathA=self._docs_a,
            CreateDirectoryW=lambda p: self._mkdir(p.wstring(p.arg(0)), 8),
            CreateDirectoryA=lambda p: self._mkdir(p.cstring(p.arg(0)), 8),
            GetFileAttributesW=lambda p: self._attrs(p.wstring(p.arg(0))),
            GetFileAttributesA=lambda p: self._attrs(p.cstring(p.arg(0))),
            GetFileAttributesExW=self._attrs_ex,
            CreateFileA=lambda p: self._open(p.cstring(p.arg(0))),
            CreateFileW=lambda p: self._open(p.wstring(p.arg(0))),
            ReadFile=self._read, WriteFile=self._write, CloseHandle=self._close,
            FlushFileBuffers=lambda p: (1, 4), GetFileSize=self._size,
            MoveFileExA=lambda p: self._move(p.cstring(p.arg(0)), p.cstring(p.arg(1)), p.arg(2)),
            MoveFileExW=lambda p: self._move(p.wstring(p.arg(0)), p.wstring(p.arg(1)), p.arg(2)),
            DeleteFileA=lambda p: self._delete(p.cstring(p.arg(0))),
            DeleteFileW=lambda p: self._delete(p.wstring(p.arg(0))),
            GetLastError=lambda p: (self.error, 0), SetLastError=self._set_error,
            FindFirstFileW=lambda p: (INVALID, 8), FindClose=lambda p: (1, 4),
            WideCharToMultiByte=self._narrow,
        )

    def _narrow(self, p):
        text = p.wstring(p.arg(2))
        data = text.encode("latin-1", "replace") + b"\0"
        if p.arg(4) and p.arg(5):
            p.write(p.arg(4), data[: p.arg(5)])
        if p.arg(7):
            p.put32(p.arg(7), 0)
        return len(data), 32

    def _set_error(self, p):
        self.error = p.arg(0)
        return 0, 4

    def _docs_w(self, p):
        p.write(p.arg(1), DOCS.encode("utf-16-le") + b"\0\0")
        return 1, 16

    def _docs_a(self, p):
        p.write(p.arg(1), DOCS.encode() + b"\0")
        return 1, 16

    def _mkdir(self, path: str, pop: int):
        key = path.lower()
        if key in self.folders:
            self.error = ERROR_ALREADY_EXISTS
            return 0, pop
        self.folders.add(key)
        return 1, pop

    def _attrs(self, path: str):
        key = path.lower()
        if key in self.files:
            return 0x80, 4
        if key in self.folders:
            return 0x10, 4
        self.error = ERROR_FILE_NOT_FOUND
        return INVALID, 4

    def _attrs_ex(self, p):
        value, _ = self._attrs(p.wstring(p.arg(0)))
        if value == INVALID:
            return 0, 12
        p.write(p.arg(2), struct.pack("<I", value) + bytes(32))
        return 1, 12

    def _open(self, path: str):
        p = self.p
        access, disposition = p.arg(1), p.arg(4)
        key = path.lower()
        if disposition == 3 and key not in self.files:          # OPEN_EXISTING
            self.error = ERROR_FILE_NOT_FOUND
            return INVALID, 28
        parent = key.rsplit("\\", 1)[0]
        if parent not in self.folders:
            self.error = ERROR_PATH_NOT_FOUND
            return INVALID, 28
        if disposition in (1, 2):                                # CREATE_NEW, CREATE_ALWAYS
            self.files[key] = b""
        handle = 0x700 + len(self.handles) * 4
        self.handles[handle] = [key, 0]
        return handle, 28

    def _read(self, p):
        key, at = self.handles[p.arg(0)]
        data = self.files[key][at:at + p.arg(2)]
        self.handles[p.arg(0)][1] += len(data)
        p.write(p.arg(1), data)
        if p.arg(3):
            p.put32(p.arg(3), len(data))
        return 1, 20

    def _write(self, p):
        key, at = self.handles[p.arg(0)]
        data = p.read(p.arg(1), p.arg(2))
        self.files[key] = self.files[key][:at] + data
        self.handles[p.arg(0)][1] += len(data)
        if p.arg(3):
            p.put32(p.arg(3), len(data))
        return 1, 20

    def _size(self, p):
        key, _ = self.handles[p.arg(0)]
        if p.arg(1):
            p.put32(p.arg(1), 0)
        return len(self.files[key]), 8

    def _close(self, p):
        self.handles.pop(p.arg(0), None)
        return 1, 4

    def _move(self, source: str, target: str, flags: int):
        s, t = source.lower(), target.lower()
        if s not in self.files:
            self.error = ERROR_FILE_NOT_FOUND
            return 0, 12
        if t in self.files and not flags & 1:                   # MOVEFILE_REPLACE_EXISTING
            self.error = ERROR_ALREADY_EXISTS
            return 0, 12
        self.files[t] = self.files.pop(s)
        return 1, 12

    def _delete(self, path: str):
        if self.files.pop(path.lower(), None) is None:
            self.error = ERROR_FILE_NOT_FOUND
            return 0, 4
        return 1, 4

    def looks_file(self, slot: int) -> str:
        return (f"{DOCS}\\LDW\\Game\\Virtual Villagers Fun Patcher\\Save {slot}\\Data\\Head Looks\\"
                f"Head Looks - Save {slot}.dat").lower()


# Each game's record table and fields (the DLL's LAYOUT; native/vvfp_head_look/vvfp_head_look.c).
GAMES = {
    5: dict(records=0x554148 + 0x48, stride=0x2F44, count=150, present=0x1CD4, name=0x1B9C, sex=0x1B90,
            age=0x1B8C, head=0x1BB8, manager=0x4DACE0, slot_field=0x17D80, table=(0x494051, 0x41F1E6, 0x48)),
    4: dict(records=0x50E568 + 0x44, stride=0x2E3C, count=150, present=0x1CC4, name=0x1B9C, sex=0x1B90,
            age=0x1B8C, head=0x1BB8, manager=0x4CB51C, slot_field=0x17114, table=(0x488D71, 0x42001C, 0x44)),
    1: dict(pool_global=0x48B614, stride=0x3D8, count=256, present=0x28, name=0x370, sex=0x350, age=0x348,
            head=0x360, manager=0x48AEDC, slot_field=0xABE4),
    2: dict(pool_global=0x499F24, stride=0xE48C, count=256, present=0x30, name=0x564, sex=0x538, age=0x530,
            head=0x548, manager=0x4997BC, slot_field=0x30378),
    3: dict(records=0x59E110 + 0x14, stride=0x1F8C, count=150, present=0xF10, name=0xDD4, sex=0xDC8,
            age=0xDC4, head=0xDF0, manager=0x4B309C, slot_field=0x12F24, table=(0x4279B4, 0x42883A, 0x14)),
}


class Game:
    """One game in the emulator with the DLL started and a village of `villagers` (name, sex, age, head)."""

    def __init__(self, game: int, exe: bytes, *, start: bool = True, slot: int = 1):
        self.game = game
        self.g = GAMES[game]
        self.p = Process(exe, DLL)
        self.disk = Disk(self.p)
        self.p.tick = 1_000_000
        self.g = dict(self.g)
        table = self.g.get("table")
        if table is not None:
            # The record table the executable itself names (native/shared/vv<N>_villager_table.h): 256
            # Villagers (Experimental) moves it to 0x800000 with 256 slots.
            manager_imm, slots_imm, base = table
            if self.p.read(manager_imm - 1, 1) == b"\xB9" and self.p.u32(manager_imm) == 0x800000 \
                    and self.p.u32(slots_imm) == 256:
                self.g.update(records=0x800000 + base, count=256)
        pool = self.g.get("pool_global")
        if pool is not None:
            # A New Home and The Lost Children keep a pointer to their 256 records.
            self.g["records"] = self.p.alloc(self.g["count"] * self.g["stride"])
            self.p.put32(pool, self.g["records"])
        if start:
            self.p.export("VvfpStartup", game, 0)
        manager = self.p.alloc(self.g["slot_field"] + 0x100)
        self.p.put32(self.g["manager"], manager)
        self.p.put32(manager + self.g["slot_field"], slot)

    def record(self, i: int) -> int:
        return self.g["records"] + i * self.g["stride"]

    def villager(self, i: int, name: str, *, age: int, head: int = 4, sex: int = 0) -> int:
        r = self.record(i)
        self.p.write(r + self.g["present"], b"\x01")
        self.p.write(r + self.g["name"], name.encode() + b"\0")
        self.p.put32(r + self.g["sex"], sex)
        self.p.put32(r + self.g["age"], age)
        self.p.put32(r + self.g["head"], head)
        return r

    def later(self) -> None:
        self.p.tick += 1000

    def look(self, i: int) -> int:
        self.later()
        return self.p.export("VvfpHeadLookGet", self.game, self.record(i))

    def set_look(self, i: int, look: int) -> int:
        self.later()
        return self.p.export("VvfpHeadLookSet", self.game, self.record(i), look)

    def run(self, start: int, *, regs: dict[str, int], until: int | None = None, count: int = 64) -> None:
        p = self.p
        p.set_reg("esp", STACK_TOP - 0x4000)
        for name, value in regs.items():
            p.set_reg(name, value)
        self.later()
        p.mu.emu_start(start, until or 0, count=count)
