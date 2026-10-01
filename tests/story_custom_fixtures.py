"""Fixtures for the Custom Island Event tests (tests/test_story_custom_island_event.py).

Each game's villager records are laid out where the game keeps them (the
static arrays of The Secret City, The Tree of Life and New Believers; the
lazily built arrays of A New Home and The Lost Children, allocated and
published through their globals), with exactly the fields the companion's
adapter for that game reads (native/vvfp_story_upgrades/story_c*.inc).

The event structures are packed exactly as story_custom.h declares them;
the tests check the layout against the test build's own sizes first.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field

KEEP = -1000000

# What each game's adapter reads.  `base` is record 0 (None: behind a
# pointer global, allocated by the fixture); `sex` is (field, male, female).
LAYOUTS = {
    "vv1": dict(n=1, stride=0x3D8, count=256, active=0x28, health=0x344, age=0x348, processed=0x34C,
                sex=(0x350, 1, 2), name=0x370, name_cap=0x1C, head=0x360, body=0x364, likes=0x398,
                dislikes=0x3A8, slots=4, prefs=46, skills=0x3BC, skill_count=5, floats=False,
                pregnant=0x358, litter=0x35C, sick=(0x354, 4), heads=20, bodies=20, adult=280,
                carrier=360),
    "vv2": dict(n=2, stride=0xE48C, count=256, active=0x30, health=0x52C, age=0x530, processed=0x534,
                sex=(0x538, 1, 2), name=0x564, name_cap=0x18, head=0x548, body=0x54C, likes=0x5F0,
                dislikes=0x6E8, slots=62, prefs=62, skills=0x7E4, skill_count=5, floats=False,
                pregnant=0x540, litter=0x544, sick=(0x53C, 4), heads=30, bodies=30, adult=280,
                carrier=360),
    "vv3": dict(n=3, base=0x59E124, stride=0x1F8C, count=150, active=0xF10, health=0xE78, age=0xDC4,
                processed=0xE74, sex=(0xDC8, 0, 1), name=0xDD4, name_cap=0x19, head=0xDF0, body=0xDF4,
                likes=0xFB4, dislikes=0xFC0, slots=3, prefs=79, skills=0xEAC, skill_count=5,
                floats=False, pregnant=0xE8C, litter=0xE90, sick=(0xE89, 1), heads=30, bodies=30,
                adult=280, carrier=360),
    "vv4": dict(n=4, base=0x50E5AC, stride=0x2E3C, count=150, active=0x1CC4, health=0x1C40,
                age=0x1B8C, processed=0x1C3C, sex=(0x1B90, 0, 1), name=0x1B9C, name_cap=0x19,
                head=0x1BB8, body=0x1BBC, likes=0x1E60, dislikes=0x1E6C, slots=3, prefs=79,
                skills=0x1C5C, skill_count=5, floats=True, pregnant=0x1C4C, litter=0x1C50,
                sick=(0x1C48, 1), heads=30, bodies=30, adult=280, carrier=360),
    "vv5": dict(n=5, base=0x554190, stride=0x2F44, count=150, active=0x1CD4, health=0x1C40,
                age=0x1B8C, processed=0x1C3C, sex=(0x1B90, 0, 1), name=0x1B9C, name_cap=0x19,
                head=0x1BB8, body=0x1BBC, likes=0x1F5C, dislikes=0x1F68, slots=3, prefs=79,
                skills=0x1C5C, skill_count=6, floats=True, pregnant=0x1C4C, litter=0x1C50,
                sick=(0x1C48, 1), heads=30, bodies=30, adult=280, carrier=280),
}

PARENTS = {
    "vv2": (0x57D, 0x596, 0x19, 0x5B0, 0x5B4, 0x5B8, 0x5BC),
    "vv3": (0xDF8, 0xE11, 0x19, 0xE2C, 0xE30, 0xE34, 0xE38),
    "vv4": (0x1BC0, 0x1BD9, 0x19, 0x1BF4, 0x1BF8, 0x1BFC, 0x1C00),
    "vv5": (0x1BC0, 0x1BD9, 0x19, 0x1BF4, 0x1BF8, 0x1BFC, 0x1C00),
}


def fnv_name(name: bytes, capacity: int) -> int:
    """native/shared/custom_titles.h vv_title_fingerprint."""
    h = 2166136261
    for b in name[:capacity]:
        if b == 0:
            break
        h = ((h ^ b) * 16777619) & 0xFFFFFFFF
    h = ((h ^ 0xFF) * 16777619) & 0xFFFFFFFF
    return h or 1


class Village:
    """One game's village in an emulated process."""

    def __init__(self, proc, game: str):
        self.proc = proc
        self.game = game
        self.L = LAYOUTS[game]
        self.world = None
        if game == "vv1":
            self.world = proc.alloc(0xB000)
            self.array = proc.alloc(0x3E034)
            proc.put32(0x48AEDC, self.world)
            proc.put32(0x48B614, self.array)
            proc.put32(self.array + 0x3E010, self.world)
            proc.put32(self.world + 0xADE8, self.array)
            proc.put32(self.world + 0x9E40, 5)            # island events so far
            proc.put32(self.world + 0xAD34, 0xFFFFFFFF)  # nobody selected
            self.base = self.array
        elif game == "vv2":
            self.world = proc.alloc(0x31000)
            self.array = proc.alloc(0xE57500)
            proc.put32(0x4997BC, self.world)
            proc.put32(0x499F24, self.array)
            proc.put32(self.array + 0xE574D4, self.world)
            proc.put32(self.world + 0x305A4, self.array)
            proc.put32(self.world + 0x2E51C, 5)
            proc.put32(self.world + 0x304F0, 0xFFFFFFFF)
            self.base = self.array
        else:
            self.base = self.L["base"]
            for i in range(self.L["count"]):
                proc.write(self.record(i), bytes(self.L["stride"]))
            if game == "vv4":
                self.world = proc.alloc(0x18000)
                proc.put32(0x4CB51C, self.world)
            if game == "vv5":
                self.world = proc.alloc(0x18000)
                proc.put32(0x4DACE0, self.world)

    def record(self, i: int) -> int:
        return self.base + i * self.L["stride"]

    def put(self, i: int, *, sex: str, years: float, name: str, health: int = 90,
            head: int = 3, body: int = 4, faction: int = 0) -> int:
        L = self.L
        r = self.record(i)
        p = self.proc
        p.write(r + L["active"], b"\1")
        p.put32(r + L["health"], health)
        age = int(years * 20)
        p.put32(r + L["age"], age)
        p.put32(r + L["processed"], age)
        off, male, female = L["sex"]
        p.put32(r + off, male if sex == "m" else female)
        p.write(r + L["name"], name.encode() + bytes(L["name_cap"] - len(name)))
        p.put32(r + L["head"], head)
        p.put32(r + L["body"], body)
        for k in range(L["slots"]):
            p.put32(r + L["likes"] + 4 * k, 0xFFFFFFFF)
            p.put32(r + L["dislikes"] + 4 * k, 0xFFFFFFFF)
        if self.game == "vv5":
            p.write(r + 0x1CEC, bytes([faction]))
            p.put32(r + 0x1CFC, 0)
        return r

    def fingerprint(self, i: int) -> int:
        return fnv_name(self.proc.read(self.record(i) + self.L["name"], self.L["name_cap"]),
                        self.L["name_cap"])

    def i32(self, i: int, off: int) -> int:
        return struct.unpack("<i", self.proc.read(self.record(i) + off, 4))[0]

    def f32(self, i: int, off: int) -> float:
        return struct.unpack("<f", self.proc.read(self.record(i) + off, 4))[0]

    def byte(self, i: int, off: int) -> int:
        return self.proc.read(self.record(i) + off, 1)[0]

    def skill(self, i: int, k: int):
        off = self.L["skills"] + 4 * k
        return self.f32(i, off) if self.L["floats"] else self.i32(i, off)

    def sick(self, i: int) -> int:
        off, size = self.L["sick"]
        return self.i32(i, off) if size == 4 else self.byte(i, off)

    def name(self, i: int) -> str:
        raw = self.proc.read(self.record(i) + self.L["name"], self.L["name_cap"])
        return raw.split(b"\0")[0].decode()

    def prefs(self, i: int, which: str):
        off = self.L[which]
        return [self.i32(i, off + 4 * k) for k in range(self.L["slots"])]


# ---- the event structures (story_custom.h) ----------------------------------

def _s(text: str, size: int) -> bytes:
    raw = text.encode("latin-1")
    assert len(raw) < size, text
    return raw + bytes(size - len(raw))


@dataclass
class Spawn:
    count: int = 1
    sex: int = 1                 # STORY_SEX_MALE 1, FEMALE 2
    age: int = 400
    name: str = ""
    head: int = KEEP
    body: int = KEEP
    prefs_set: int = 0
    likes: tuple = (-1, -1, -1)
    dislikes: tuple = (-1, -1, -1)
    skills: tuple = (KEEP,) * 6
    title: str = ""
    mask: int = KEEP
    faction: int = KEEP

    def pack(self) -> bytes:
        return (struct.pack("<3i", self.count, self.sex, self.age) + _s(self.name, 24)
                + struct.pack("<3i", self.head, self.body, self.prefs_set)
                + struct.pack("<3i", *self.likes) + struct.pack("<3i", *self.dislikes)
                + struct.pack("<6i", *self.skills) + _s(self.title, 32)
                + struct.pack("<2i", self.mask, self.faction))


@dataclass
class Change:
    index: int
    fingerprint: int
    fate: int = 0
    sick: int = 0
    litter: int = 0
    father: int = -1
    father_fingerprint: int = 0
    head: int = KEEP
    body: int = KEEP
    like_add: int = -1
    like_remove: int = -1
    dislike_add: int = -1
    dislike_remove: int = -1
    skills: tuple = (KEEP,) * 6
    title_op: int = 0
    title: str = ""
    mask: int = KEEP
    status: int = KEEP
    behaviour: int = KEEP
    parents_set: int = 0
    father_name: str = ""
    mother_name: str = ""
    father_head: int = KEEP
    father_body: int = KEEP
    mother_head: int = KEEP
    mother_body: int = KEEP

    def pack(self) -> bytes:
        return (struct.pack("<iIiiiiI", self.index, self.fingerprint, self.fate, self.sick, self.litter,
                            self.father, self.father_fingerprint)
                + struct.pack("<6i", self.head, self.body, self.like_add, self.like_remove,
                              self.dislike_add, self.dislike_remove)
                + struct.pack("<6i", *self.skills) + struct.pack("<i", self.title_op)
                + _s(self.title, 32)
                + struct.pack("<4i", self.mask, self.status, self.behaviour, self.parents_set)
                + _s(self.father_name, 24) + _s(self.mother_name, 24)
                + struct.pack("<4i", self.father_head, self.father_body, self.mother_head,
                              self.mother_body))


@dataclass
class Event:
    game: int = 0
    title: str = "A Strange Day"
    text: str = "Something happened."
    food_op: int = 0
    food_amount: int = 0
    tech_op: int = 0
    tech_amount: int = 0
    refill: int = 0
    village: int = 0
    spawns: list = field(default_factory=list)
    changes: list = field(default_factory=list)

    SIZE = 4 + 48 + 600 + 4 * 7 + 8 * 136 + 4 + 256 * 192

    def pack(self) -> bytes:
        out = struct.pack("<i", self.game) + _s(self.title, 48) + _s(self.text, 600)
        out += struct.pack("<7i", self.food_op, self.food_amount, self.tech_op, self.tech_amount,
                           self.refill, self.village, len(self.spawns))
        spawns = b"".join(s.pack() for s in self.spawns)
        out += spawns + bytes(8 * 136 - len(spawns))
        out += struct.pack("<i", len(self.changes))
        changes = b"".join(c.pack() for c in self.changes)
        out += changes + bytes(256 * 192 - len(changes))
        assert len(out) == self.SIZE
        return out


RESULT_FIELDS = ("changed", "skipped", "died", "vanished", "conceived", "no_room_babies", "born",
                 "no_room_spawns", "refused", "food_before", "food_after", "tech_before", "tech_after")


def unpack_result(raw: bytes) -> dict:
    return dict(zip(RESULT_FIELDS, struct.unpack("<13i", raw)))


class MemoryFiles:
    """The file APIs the custom titles use (native/shared/sidecar_io.h), over
    an in-memory folder, so the emulated companion publishes and reads real
    bytes the test can inspect."""

    def __init__(self, proc):
        self.proc = proc
        self.files: dict[str, bytes] = {}
        self.handles: dict[int, list] = {}
        self.next = 0x100
        self.last_error = 0
        for name in ("CreateFileA", "ReadFile", "WriteFile", "CloseHandle", "FlushFileBuffers",
                     "MoveFileExA", "DeleteFileA", "GetFileAttributesA", "GetLastError"):
            proc.api_handlers[name] = getattr(self, "_" + name)

    def _CreateFileA(self, p):
        path = p.cstring(p.arg(0)).lower()
        disposition = p.arg(4)
        if disposition == 3:            # OPEN_EXISTING
            if path not in self.files:
                self.last_error = 2
                return 0xFFFFFFFF, 28
        else:                           # CREATE_ALWAYS
            self.files[path] = b""
        handle = self.next
        self.next += 4
        self.handles[handle] = [path, 0]
        return handle, 28

    def _ReadFile(self, p):
        path, pos = self.handles[p.arg(0)]
        data = self.files[path][pos:pos + p.arg(2)]
        p.write(p.arg(1), data)
        p.put32(p.arg(3), len(data))
        self.handles[p.arg(0)][1] += len(data)
        return 1, 20

    def _WriteFile(self, p):
        path, pos = self.handles[p.arg(0)]
        data = p.read(p.arg(1), p.arg(2))
        self.files[path] += data
        p.put32(p.arg(3), len(data))
        return 1, 20

    def _CloseHandle(self, p):
        self.handles.pop(p.arg(0), None)
        return 1, 4

    def _FlushFileBuffers(self, p):
        return 1, 4

    def _MoveFileExA(self, p):
        source = p.cstring(p.arg(0)).lower()
        target = p.cstring(p.arg(1)).lower()
        if source not in self.files or (target in self.files and not p.arg(2) & 1):
            self.last_error = 183
            return 0, 12
        self.files[target] = self.files.pop(source)
        return 1, 12

    def _DeleteFileA(self, p):
        return (1 if self.files.pop(p.cstring(p.arg(0)).lower(), None) is not None else 0), 4

    def _GetFileAttributesA(self, p):
        if p.cstring(p.arg(0)).lower() in self.files:
            return 0x80, 4
        self.last_error = 2
        return 0xFFFFFFFF, 4

    def _GetLastError(self, p):
        return self.last_error, 0

    def titles(self, path: str):
        raw = self.files.get(path.lower())
        if raw is None:
            return None
        magic, version, game, count = struct.unpack("<4I", raw[:16])
        assert (magic, version) == (0x31544356, 1)
        out = []
        for k in range(count):
            e = raw[16 + 40 * k:56 + 40 * k]
            index, fp = struct.unpack("<2I", e[:8])
            out.append((index, fp, e[8:].split(b"\0")[0].decode()))
        return game, out
