"""The emulated A New Home / The Lost Children for tests/test_sex_change_vv1_origins.py and
tests/test_sex_change_vv2_origins.py: the stock executable with "VVFP VV1 Origins Icons.dll" or
"VVFP VV2 Origins Icons.dll" mapped beside it in tests/story_emulator.py, a village in the game's own record
table, the game's save slot, the exe-side mask memory the patcher's exe patch appends (A New Home's .vv1md
scratch at 0x491000, The Lost Children's .mtab at 0x4B3000), and the small disk of tests/head_look_emulation.py
-- so the masks, their file and the slot's "Sex Changes" log are the DLL's own code end to end."""
from __future__ import annotations

import struct
from pathlib import Path

from story_emulator import Process
from head_look_emulation import DOCS, Disk

ROOT = Path(__file__).resolve().parents[1]

GAMES = {
    1: dict(dll=ROOT / "assets" / "origins" / "VVFP VV1 Origins Icons.dll", pool=0x48B614, stride=0x3D8,
            count=256, present=0x28, name=0x370, name_bytes=0x1C, sex=0x350, family=0x36C, pregnant=0x358,
            male=1, female=2, save_manager=0x48AEDC, slot_field=0xABE4, scratch=(0x491000, 0x1000),
            masks_file="Virtual Villagers 1 Village Masks - Save {slot}.dat"),
    2: dict(dll=ROOT / "assets" / "origins" / "VVFP VV2 Origins Icons.dll", pool=0x499F24, stride=0xE48C,
            count=256, present=0x30, name=0x564, name_bytes=0x18, sex=0x538, father=0x57D, mother=0x596,
            pregnant=0x540, male=1, female=2, save_manager=0x4997BC, slot_field=0x30378,
            scratch=(0x4B3000, 0x1000), masks_file="Virtual Villagers 2 Village Masks - Save {slot}.dat"),
}

VV1_TABLE, VV1_MANAGER, VV1_SLOT = 0x491000, 0x491098, 0x4911F4
VV2_TABLE, VV2_SLOT = 0x4B3000, 0x4B3F10
VV2_RECORD_ARRAY_FN = 0x0044F4E0


def fnv_text(h: int, data: bytes, capacity: int) -> int:
    for b in data[:capacity]:
        if b == 0:
            break
        h = ((h ^ b) * 16777619) & 0xFFFFFFFF
    return h


def fnv_bytes(h: int, data: bytes) -> int:
    for b in data:
        h = ((h ^ b) * 16777619) & 0xFFFFFFFF
    return h


def masks_path(game: int, slot: int) -> str:
    return (f"{DOCS}\\LDW\\Game\\Virtual Villagers Fun Patcher\\Save {slot}\\Data\\Village Masks\\"
            + GAMES[game]["masks_file"].format(slot=slot)).lower()


def log_path(slot: int) -> str:
    return (f"{DOCS}\\LDW\\Game\\Virtual Villagers Fun Patcher\\Save {slot}\\Data\\"
            f"Sex Changes\\Sex Changes - Save {slot}.txt").lower()


class Village:
    """One game in the emulator with its Origins DLL and a village of villagers."""

    def __init__(self, game: int, exe: bytes, *, slot: int = 1, disk: Disk | None = None):
        self.game = game
        self.g = GAMES[game]
        self.slot = slot
        self.p = Process(exe, self.g["dll"])
        self.disk = Disk(self.p)
        if disk is not None:
            self.disk.files = dict(disk.files)
            self.disk.folders = set(disk.folders)
        h = self.p.api_handlers
        h["SHGetFolderPathA"] = self._docs_folder
        h["MoveFileA"] = lambda p: self.disk._move(p.cstring(p.arg(0)), p.cstring(p.arg(1)), 0)
        h["GetFileAttributesA"] = lambda p: self.disk._attrs(p.cstring(p.arg(0)))
        # The game-start installs a sweep reaches (the cross-check's stub page) get no memory here: each
        # fails closed, and the masks are what is tested.
        h["VirtualAlloc"] = lambda p: (0, 16)
        self.p.tick = 1_000_000
        lo, size = self.g["scratch"]
        if not self.p.mapped(lo, size):
            self.p.mu.mem_map(lo, size)
        self.p.write(lo, bytes(size))
        self.records = self.p.alloc(self.g["count"] * self.g["stride"])
        self.p.put32(self.g["pool"], self.records)
        manager = self.p.alloc(self.g["slot_field"] + 0x100)
        self.p.put32(self.g["save_manager"], manager)
        self.p.put32(manager + self.g["slot_field"], slot)
        if game == 1:
            self.p.put32(VV1_MANAGER, self.records)
            self.p.put32(VV1_SLOT, slot)
        else:
            self.p.put32(VV2_SLOT, slot)
            self.p.stub(VV2_RECORD_ARRAY_FN, lambda p: (self.records, 0))

    def _docs_folder(self, p):
        p.write(p.arg(4), DOCS.encode() + b"\0")
        return 0, 20

    # ---- the village --------------------------------------------------
    def record(self, i: int) -> int:
        return self.records + i * self.g["stride"]

    def villager(self, i: int, name: str, sex: int, *, family: int = 0, parents: tuple[str, str] = ("", "")):
        r = self.record(i)
        self.p.write(r + self.g["present"], b"\x01")
        self.p.write(r + self.g["name"], name.encode() + b"\0")
        self.p.put32(r + self.g["sex"], sex)
        if self.game == 1:
            self.p.put32(r + self.g["family"], family)
        else:
            self.p.write(r + self.g["father"], parents[0].encode() + b"\0")
            self.p.write(r + self.g["mother"], parents[1].encode() + b"\0")
        return r

    def identity(self, i: int) -> int:
        g, r = self.g, self.record(i)
        data = self.p.read(r, g["stride"])
        h = fnv_text(2166136261, data[g["name"]:], g["name_bytes"])
        h = ((h ^ 0xFF) * 16777619) & 0xFFFFFFFF
        h = fnv_bytes(h, data[g["sex"]:g["sex"] + 4])
        if self.game == 1:
            h = fnv_bytes(h, data[g["family"]:g["family"] + 4])
        else:
            h = fnv_text(h, data[g["father"]:], 0x18)
            h = ((h ^ 0xFE) * 16777619) & 0xFFFFFFFF
            h = fnv_text(h, data[g["mother"]:], 0x18)
            h = ((h ^ 0xFD) * 16777619) & 0xFFFFFFFF
        return h or 1

    # ---- the masks ----------------------------------------------------
    def later(self) -> None:
        self.p.tick += 5000

    def load(self) -> None:
        """The game's load: the sidecar read for the village on screen (A New Home's Vv1MaskRestore; The Lost
        Children's per-frame sweep, whose first frame binds the village and reads the file)."""
        self.later()
        if self.game == 1:
            self.p.export("Vv1MaskRestore")
        else:
            self.p.export("Vv2MaskSweep", self.records)

    def frame(self) -> None:
        """One village frame (The Lost Children's sweep: the village sync follows the roster)."""
        self.later()
        if self.game == 2:
            self.p.export("Vv2MaskSweep", self.records)

    def put_mask(self, i: int, mask: int) -> None:
        """A mask chosen in Change Appearance: the table entry, then the file (the story host's way)."""
        if self.game == 1:
            at = VV1_TABLE + (i >> 1)
            b = self.p.read(at, 1)[0]
            b = (b & 0x0F) | (mask << 4) if i & 1 else (b & 0xF0) | mask
            self.p.write(at, bytes([b]))
        else:
            self.p.write(VV2_TABLE + i, bytes([mask]))

    def mask(self, i: int) -> int:
        return self.p.export("VvfpMaskOf", self.record(i))

    def change(self, i: int) -> int:
        """The sex field flipped as native/shared/sex_change.h writes it, and the DLL told."""
        g, r = self.g, self.record(i)
        before = self.p.alloc(g["stride"])
        self.p.write(before, self.p.read(r, g["stride"]))
        now = self.p.u32(r + g["sex"])
        self.p.put32(r + g["sex"], g["male"] if now == g["female"] else g["female"])
        return self.p.export("VvfpVillagerSexChanged", self.game, self.slot, r, before)

    def file_roster(self) -> list[int]:
        data = self.disk.files[masks_path(self.game, self.slot)]
        if self.game == 1:
            return list(struct.unpack_from("<256I", data, 4 + 128))
        return list(struct.unpack_from("<256I", data, 4))
