"""The Custom Titles file (native/shared/custom_titles.h), read and written as the Story / Cheat
Upgrades companion does: "Custom Titles - Save N.dat" beside the saves.

Version 3 (v1.35.70): 84-byte entries -- the record index (or PENDING), the fingerprint (name, likes,
dislikes: vv_title_identity), flags (KNOWN: the looks were read from the villager), the age, head, body
and sex, six skill dwords, the title.  A PENDING title is one whose villager could not be told apart
after a load: shown on nobody, never dropped for it, bound again by the companion once exactly one
villager has the whole identity.  Version 2 (40-byte entries: index, fingerprint, title) is still read,
each entry bound with its looks not known; anything written here is version 3.

read() accepts exactly what the companion's vv_titles_validate accepts, so nothing reads a file the
game would set aside.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field

MAGIC = b"VCT1"
VERSION, VERSION_2 = 3, 2
HEADER = 16
ENTRY = {VERSION: 84, VERSION_2: 40}
TITLE_BYTES, TITLES_MAX = 32, 256
SKILLS = 6
PENDING = 0xFFFFFFFF
KNOWN = 1
SLOTS = {1: 256, 2: 256, 3: 256, 4: 256, 5: 256}   # the most records any build of the game has

# Where each game keeps the looks in a SAVED villager, relative to the name (the record's own fields:
# the Custom Island Event adapters' offsets, story_c*.inc; scripts/vvfp_consistency_check.py LAYOUTS
# for The Lost Children to New Believers): age, sex, head, body, skills, skill count, float skills.
SAVE_LOOKS = {
    1: (0x348 - 0x370, 0x350 - 0x370, 0x360 - 0x370, 0x364 - 0x370, 0x3BC - 0x370, 5, False),
    2: (-0x34, -0x2C, -0x1C, -0x18, 0x280, 5, False),
    3: (-0x10, -0x0C, 0x1C, 0x20, 0xD8, 5, False),
    4: (-0x10, -0x0C, 0x1C, 0x20, 0xC0, 5, True),
    5: (-0x10, -0x0C, 0x1C, 0x20, 0xC0, 6, True),
}


@dataclass
class Entry:
    index: int                              # the record, or PENDING
    identity: int                           # the fingerprint
    title: str
    known: bool = False
    age: int = 0
    head: int = 0
    body: int = 0
    sex: int = 0
    skills: tuple = field(default=(0,) * SKILLS)   # raw dwords

    @property
    def pending(self) -> bool:
        return self.index == PENDING

    def skill_values(self, game: int, rounded: bool = False) -> list[float]:
        """The skills as numbers (the game's own count, floats where the game keeps floats; `rounded`
        to two places, for the words of a report only)."""
        count, floats = SAVE_LOOKS[game][5], SAVE_LOOKS[game][6]
        raw = self.skills[:count]
        if floats:
            values = [struct.unpack("<f", struct.pack("<I", v))[0] for v in raw]
            return [round(v, 2) for v in values] if rounded else values
        return [struct.unpack("<i", struct.pack("<I", v))[0] for v in raw]


def title_valid(title: bytes) -> bool:
    """custom_titles.h vv_title_valid on the stored 32 bytes."""
    end = title.find(b"\0")
    if end < 1 or end > TITLE_BYTES - 1:
        return False
    text = title[:end]
    return all(0x20 <= c <= 0x7E for c in text) and text.strip(b" ") != b""


def read(data: bytes, game: int, slots: int | None = None) -> tuple[int, list[Entry]] | None:
    """(version, entries) of a file the companion would load for this game, else None."""
    slots = SLOTS[game] if slots is None else slots
    if len(data) < HEADER or data[:4] != MAGIC:
        return None
    version, file_game, count = struct.unpack_from("<III", data, 4)
    if file_game != game or version not in ENTRY:
        return None
    size = ENTRY[version]
    if count > TITLES_MAX or len(data) != HEADER + count * size:
        return None
    out: list[Entry] = []
    bound: set[int] = set()
    for k in range(count):
        e = data[HEADER + k * size:HEADER + (k + 1) * size]
        index, identity = struct.unpack_from("<II", e)
        if index == PENDING:
            if version != VERSION:
                return None
        elif index >= slots or index in bound:
            return None
        if identity == 0 or not title_valid(e[size - TITLE_BYTES:]):
            return None
        title = e[size - TITLE_BYTES:].split(b"\0", 1)[0].decode("ascii")
        if version == VERSION:
            flags = struct.unpack_from("<I", e, 8)[0]
            if flags & ~KNOWN or (not flags & KNOWN and any(e[12:52])):
                return None
            age, head, body, sex = struct.unpack_from("<4i", e, 12)
            skills = struct.unpack_from(f"<{SKILLS}I", e, 28)
            out.append(Entry(index, identity, title, bool(flags & KNOWN), age, head, body, sex, tuple(skills)))
        else:
            out.append(Entry(index, identity, title))
        if index != PENDING:
            bound.add(index)
    return version, out


def entry_bytes(e: Entry, version: int = VERSION) -> bytes:
    title = e.title.encode("ascii").ljust(TITLE_BYTES, b"\0")
    if version == VERSION_2:
        if e.pending:
            raise ValueError("a version 2 file holds no pending title")
        return struct.pack("<II", e.index, e.identity) + title
    looks = struct.pack("<4i", e.age, e.head, e.body, e.sex) + struct.pack(f"<{SKILLS}I", *e.skills) \
        if e.known else bytes(40)
    return struct.pack("<III", e.index, e.identity, KNOWN if e.known else 0) + looks + title


def serialise(game: int, entries: list[Entry], version: int = VERSION) -> bytes:
    """A version 3 file (custom_titles.h vv_titles_serialise) -- or, to change a version 2 file and keep
    every other entry byte for byte, version 2 (the companion writes it back as version 3 at its next
    load)."""
    return MAGIC + struct.pack("<III", version, game, len(entries)) + b"".join(entry_bytes(e, version)
                                                                             for e in entries)


def looks_from_save(game: int, data: bytes, at: int) -> dict:
    """The saved villager's looks (whose name is at `at`), as an Entry keeps them."""
    age, sex, head, body, skills, count, _floats = SAVE_LOOKS[game]
    raw = [struct.unpack_from("<I", data, at + skills + 4 * k)[0] for k in range(count)]
    return dict(age=struct.unpack_from("<i", data, at + age)[0], head=struct.unpack_from("<i", data, at + head)[0],
                body=struct.unpack_from("<i", data, at + body)[0], sex=struct.unpack_from("<i", data, at + sex)[0],
                skills=tuple(raw + [0] * (SKILLS - count)))


def could_be(game: int, e: Entry, looks: dict) -> bool:
    """custom_titles.h vv_title_looks_could_be: the same head, body and sex, no younger, no skill lower
    (an entry whose looks are not known: anyone of its fingerprint)."""
    if not e.known:
        return True
    if (looks["head"], looks["body"], looks["sex"]) != (e.head, e.body, e.sex) or looks["age"] < e.age:
        return False
    stored = e.skill_values(game)
    now = Entry(0, 1, "x", True, skills=looks["skills"]).skill_values(game)
    return all(n >= s for n, s in zip(now, stored))
