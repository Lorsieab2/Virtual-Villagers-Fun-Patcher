"""Repair Saves & Logs: revival snapshots for villagers who left before the snapshots existed (all five games).

The owner (2026-11-26): "repair logs/saves should also retroactively make revival files for any deceased/disappeared
villagers. anything that has villager data. for saves made before the patch".  Since v1.35.101 "VVFP Cause of
Death.dll" keeps every departing villager's complete record for Revive Buried/Disappeared Villagers
(native/shared/revive_snapshot.h); this makes the same snapshot, afterwards, for every Death and Disappeared record
of the slot's logs that has none, from the richest source there is:

  1. a stale copy of their entry still inside the slot's save -- the game writes each villager's entry and leaves
     copies of the dead past the end of its list (the memory rule "saves hold stale villager records"; the game's
     loader never reads them);
  2. their entry in an older save of the same village: the patcher's Backups folders, and the game's own extra
     generations of the slot (slot + 20, slot + 40) -- a save made while they were alive.

A saved entry IS the bytes the snapshot keeps: each game's writer packs exactly the record windows the snapshot
holds (revive_snapshot.h VV_RS_SAVED_*), so the snapshot's data is the entry's, byte for byte, rearranged into the
windows' order (ENTRY_TO_DATA).  Nothing is inferred into it: what the source does not hold is not made up.

WHO IS WHO (never by slot alone: records are reused and stale).  A source entry is the departed villager when its
name, sex, head, body, likes and dislikes are theirs (the eight-field key, less the age, which is only known as an
upper bound: the entry's age must be no older than the age at death, and the parents' names must agree where a
log names them).  Of several such entries the oldest-aged (newest) is taken; when two of the same age differ in
anything persistent, nobody is guessed: none is made.  Each entry is used for one departure at most.

EXACT.  The identity fields (name, sex, looks, personal number, family, parents, likes, dislikes) of a matched
entry are the villager's own.  The skills, job preference, titles, Faith, masks and role are as they were when the
source was saved: "exact" (VV_RS_EXACT_LATER) only when the entry's age is the age at death (a body's copy).
The snapshot says its source and time (vv_rs_entry.source, when), and Revive says what is guaranteed.

NEVER: a save or a backup is only read; the snapshot file is the patcher's own (written through "<name>.tmp", then
moved); a file the DLL would not read is never written over.  A later capture at a real departure always wins
over a backfill (story_revive.inc rv_match_snaps).  Running it again changes nothing: a departure that already has
a snapshot (captured or backfilled) gets no other.  The logs' repeats are repeats: each person once.
"""
from __future__ import annotations

import os
import struct
from dataclasses import dataclass, field
from pathlib import Path

import vv_save_layout as layout

DATA = "Virtual Villagers Fun Patcher Data"
RELATIVE = DATA + r"\Revive Snapshots\Virtual Villagers {game} Revive Snapshots - Save {slot}.dat"
MAGIC = 0x31535256                  # 'VRS1'
VERSION = 1
HEADER = 16
MAX_ENTRIES = 2048                  # VV_RS_MAX
DATA_MAX = 0x300                    # VV_RS_DATA_MAX
NAME = 32
CAPTURED, FROM_SAVE, FROM_BACKUP = 0, 1, 2
EXACT_IDENTITY, EXACT_LATER = 0x01, 0x02
# vv_rs_entry: check, game, bytes, flags, source, exact, when_lo, when_hi, head_look, presentation, mask, traits,
# parent_looks[4], father[32], mother[32], data[0x300]
ENTRY_HEAD = struct.Struct("<IIIIIIIIiiiI4i32s32s")
ENTRY = ENTRY_HEAD.size + DATA_MAX

# The saved windows, record offsets, in the snapshot's order (revive_snapshot.h VV_RS_SAVED_*).
SAVED = {
    1: ((0x33C, 0x98),),
    2: ((0x524, 0x2DC),),
    3: ((0xDC4, 0xA8), (0xE6C, 0x40), (0xEAC, 0x18), (0xFB4, 0x0C), (0xFC0, 0x0C)),
    4: ((0x1B8C, 0xA8), (0x1C34, 0x28), (0x1C5C, 0x18), (0x1E60, 0x18)),
    5: ((0x1B8C, 0xA8), (0x1C34, 0x28), (0x1C5C, 0x1C), (0x1CEC, 0x0C), (0x1CFC, 0x04), (0x1F5C, 0x18)),
}
# The record offsets the matching reads (revive_snapshot.h VV_RS_LAYOUT): age, sex, name, name bytes, head, body,
# likes, dislikes, slots, father's and mother's names (0 none).
LAYOUT = {
    1: (0x348, 0x350, 0x370, 0x1C, 0x360, 0x364, 0x398, 0x3A8, 4, 0, 0),
    2: (0x530, 0x538, 0x564, 0x18, 0x548, 0x54C, 0x5F0, 0x6E8, 62, 0x57D, 0x596),
    3: (0xDC4, 0xDC8, 0xDD4, 0x19, 0xDF0, 0xDF4, 0xFB4, 0xFC0, 3, 0xDF8, 0xE11),
    4: (0x1B8C, 0x1B90, 0x1B9C, 0x19, 0x1BB8, 0x1BBC, 0x1E60, 0x1E6C, 3, 0x1BC0, 0x1BD9),
    5: (0x1B8C, 0x1B90, 0x1B9C, 0x19, 0x1BB8, 0x1BBC, 0x1F5C, 0x1F68, 3, 0x1BC0, 0x1BD9),
}
SEX_VALUES = {1: (1, 2), 2: (1, 2), 3: (0, 1), 4: (0, 1), 5: (0, 1)}   # (male, female)
# Where each game's saved entry starts, relative to the villager's name in it, and its length.
ENTRY_FROM_NAME = {1: 0x370 - 0x33C, 2: 0x564 - 0x524, 3: 0x14, 4: 0x14, 5: 0x20}
ENTRY_BYTES = {1: 0x98, 2: 0x2DC, 3: 0x11C, 4: 0x104, 5: 0x118}


def entry_to_data(game: int, e: bytes) -> bytes:
    """A saved entry's bytes as the snapshot keeps them (the windows in order).  Each game's own loader is the
    map: A New Home 0x43B8C0 and The Lost Children 0x44B640 copy the entry whole; The Secret City 0x456830 and The
    Tree of Life 0x45DBE0 skip a dword flag; New Believers 0x466B60 reads +0x10.. and its faction, masks, Faith,
    cooldown and role from the entry's head and tail."""
    if game in (1, 2):
        return bytes(e[:ENTRY_BYTES[game]])
    if game in (3, 4):
        return bytes(e[4:ENTRY_BYTES[game]])
    return (bytes(e[0x10:0xB8]) + bytes(e[0xB8:0xE0]) + bytes(e[0xE0:0xFC])
            + bytes(e[1:5]) + bytes(e[8:12]) + bytes(e[0x114:0x118])   # +0x1CEC..+0x1CF7
            + bytes(e[0xC:0x10])                                      # +0x1CFC role
            + bytes(e[0xFC:0x114]))                                   # likes, dislikes


def data_at(game: int, data: bytes, offset: int, size: int) -> bytes | None:
    """Record offset `offset` in a snapshot's data (vv_rs_at)."""
    at = 0
    for start, length in SAVED[game]:
        if start <= offset and offset + size <= start + length:
            return data[at + offset - start: at + offset - start + size]
        at += length
    return None


def _i32(game: int, data: bytes, offset: int) -> int | None:
    raw = data_at(game, data, offset, 4)
    return struct.unpack("<i", raw)[0] if raw is not None else None


def _text(raw: bytes | None) -> str:
    return raw.split(b"\0", 1)[0].decode("latin-1") if raw is not None else ""


def _fnv(data: bytes) -> int:
    h = 2166136261
    for b in data:
        h = ((h ^ b) * 16777619) & 0xFFFFFFFF
    return h or 1


@dataclass
class Snapshot:
    game: int
    data: bytes
    source: int = CAPTURED
    exact: int = EXACT_IDENTITY | EXACT_LATER
    when: int = 0                       # FILETIME
    flags: int = 0
    head_look: int = -1
    presentation: int = -1
    mask: int = -1
    traits: int = 0
    parent_looks: tuple = (-1, -1, -1, -1)
    father: bytes = b""
    mother: bytes = b""

    def pack(self) -> bytes:
        body = ENTRY_HEAD.pack(0, self.game, sum(n for _o, n in SAVED[self.game]), self.flags, self.source,
                               self.exact, self.when & 0xFFFFFFFF, self.when >> 32, self.head_look,
                               self.presentation, self.mask, self.traits, *self.parent_looks,
                               self.father[:NAME - 1].ljust(NAME, b"\0"), self.mother[:NAME - 1].ljust(NAME, b"\0"))
        body += self.data.ljust(DATA_MAX, b"\0")
        return struct.pack("<I", _fnv(body[4:])) + body[4:]

    def identity(self) -> tuple:
        age, sex, name, cap, head, body, likes, dislikes, slots, father, mother = LAYOUT[self.game]
        d = self.data
        return (_text(data_at(self.game, d, name, cap)), _i32(self.game, d, sex), _i32(self.game, d, head),
                _i32(self.game, d, body),
                tuple(sorted(x for x in struct.unpack(f"<{slots}i", data_at(self.game, d, likes, 4 * slots)) if x >= 0)),
                tuple(sorted(x for x in struct.unpack(f"<{slots}i", data_at(self.game, d, dislikes, 4 * slots))
                             if x >= 0)))

    def age(self) -> int | None:
        return _i32(self.game, self.data, LAYOUT[self.game][0])

    def parents(self) -> tuple[str, str]:
        _a, _s, _n, _c, _h, _b, _l, _d, _slots, father, mother = LAYOUT[self.game]
        if not father:
            return ("", "")
        return (_text(data_at(self.game, self.data, father, 0x19)), _text(data_at(self.game, self.data, mother, 0x19)))


def parse(raw: bytes, game: int) -> list[Snapshot] | None:
    """The file's snapshots, or None when the DLL would not read it (revive_snapshot.h vv_rs_file_valid)."""
    if len(raw) < HEADER:
        return None
    magic, version, file_game, count = struct.unpack_from("<4I", raw)
    if (magic != MAGIC or version != VERSION or file_game != game or count > MAX_ENTRIES
            or len(raw) != HEADER + count * ENTRY):
        return None
    out = []
    want = sum(n for _o, n in SAVED[game])
    for k in range(count):
        e = raw[HEADER + k * ENTRY: HEADER + (k + 1) * ENTRY]
        (check, g, nbytes, flags, source, exact, lo, hi, head_look, presentation, mask, traits, *rest) = \
            ENTRY_HEAD.unpack_from(e)
        looks, father, mother = tuple(rest[:4]), rest[4], rest[5]
        if (g != game or nbytes != want or source > FROM_BACKUP or check != _fnv(e[4:])
                or father[NAME - 1] != 0 or mother[NAME - 1] != 0):
            return None
        out.append(Snapshot(game, bytes(e[ENTRY_HEAD.size:ENTRY_HEAD.size + want]), source, exact, lo | hi << 32,
                            flags, head_look, presentation, mask, traits, looks, father.rstrip(b"\0"),
                            mother.rstrip(b"\0")))
    return out


def build(game: int, snapshots: list[Snapshot]) -> bytes:
    return struct.pack("<4I", MAGIC, VERSION, game, len(snapshots)) + b"".join(s.pack() for s in snapshots)


def path(folder: Path, game: int, slot: int) -> Path:
    return layout.route(Path(folder), RELATIVE.format(game=game, slot=slot))


def _write(target: Path, data: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    try:
        with open(temporary, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    except OSError:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------------------------------
# The sources: every villager entry a save holds, stale copies included
# ---------------------------------------------------------------------------------------------------

def save_entries(game: int, data: bytes) -> list[bytes]:
    """Every villager entry the save holds, as the snapshot keeps it: the ones the game loads AND the stale copies
    after them (the game never reads those; they hold the dead).  Plausible entries only (a name, a sex, looks)."""
    import vv_log_tools as tools
    checker = tools.load_checker()
    out = []
    if game == 1:
        for i in range(256):
            at = checker.VV1_BLOCK0 + i * checker.VV1_STRIDE
            e = data[at:at + 0x98]
            if len(e) == 0x98 and _plausible(1, entry_to_data(1, e)):
                out.append(entry_to_data(1, e))
        return out
    lay = checker.LAYOUTS[game]
    try:
        names = checker.villager_offsets(game, data, [])
    except ValueError:
        return out
    if not names:
        return out
    starts = [names[0]]
    if game != 2 and len(data) > checker.STOCK_SAVE[game]:
        extra = [p for p in names if p >= checker.STOCK_SAVE[game]]
        if extra:
            starts.append(extra[0])
    slots = {2: 256}.get(game, 150)
    for first in starts:
        for k in range(slots):
            p = first + k * lay.stride
            e = data[p - ENTRY_FROM_NAME[game]: p - ENTRY_FROM_NAME[game] + ENTRY_BYTES[game]]
            if p - ENTRY_FROM_NAME[game] < 0 or len(e) < ENTRY_BYTES[game]:
                break
            if checker.plausible(data, p, lay, checker.ANY_NAME_RE) and _plausible(game, entry_to_data(game, e)):
                out.append(entry_to_data(game, e))
    return out


def _plausible(game: int, d: bytes) -> bool:
    age, sex, name, cap, head, body, *_ = LAYOUT[game]
    s = Snapshot(game, d)
    who = s.identity()
    return bool(who[0]) and who[1] in SEX_VALUES[game] and 0 <= (who[2] or -1) < 64 and 0 <= (who[3] or -1) < 64 \
        and (s.age() or -1) >= 0


@dataclass
class Source:
    kind: int                           # FROM_SAVE / FROM_BACKUP
    when: int                           # FILETIME of the save file
    label: str
    entries: list[bytes]


def _filetime(p: Path) -> int:
    return int(p.stat().st_mtime * 10_000_000) + 116444736000000000


def sources(folder: Path, game: int, slot: int) -> list[Source]:
    """The slot's save (its stale copies), then the same village's older saves: the game's own extra generations of
    the slot and the patcher's backups, newest first.  Read only."""
    import vv_save_backup as backups
    import vv_last_names as ln
    folder = Path(folder)
    save = ln.save_path(folder, game, slot)
    out = []
    if not save.is_file():
        return out
    village = backups.read_village_name(game, save)
    out.append(Source(FROM_SAVE, _filetime(save), "the save", save_entries(game, save.read_bytes())))
    older: list[tuple[int, Path, str]] = []
    for extra in (slot + 20, slot + 40):
        p = save.with_name(save.name[:-len(f"{slot}.ldw")] + f"{extra}.ldw")
        if p.is_file():
            older.append((_filetime(p), p, f"the game's own copy {p.name}"))
    try:
        listed = backups.list_backups(folder)
    except (OSError, backups.BackupError):
        listed = []
    for info in listed:
        try:
            contents = backups.backup_contents(info.path)
        except OSError:
            continue
        for relative, file in contents.items():
            if Path(relative).name.lower() == save.name.lower() and Path(file).is_file():
                older.append((_filetime(Path(file)), Path(file), f"backup {info.path.name}"))
    for when, p, label in sorted(older, key=lambda t: -t[0]):
        if village is not None and backups.read_village_name(game, p) != village:
            continue                    # another village once in this slot (Start Over): never its people
        try:
            out.append(Source(FROM_BACKUP, when, label, save_entries(game, p.read_bytes())))
        except OSError:
            continue
    return out


# ---------------------------------------------------------------------------------------------------
# The departed, from the logs
# ---------------------------------------------------------------------------------------------------

@dataclass
class Departed:
    name: str
    sex: int
    age: int
    head: int
    body: int
    likes: tuple | None                 # sorted indices; None: the log does not list them
    dislikes: tuple | None
    father: str = ""
    mother: str = ""
    heading: str = ""


def departed(folder: Path, game: int, slot: int) -> list[Departed]:
    """Each person of the Deaths and Disappeared records, once (their newest record; repeats are repeats)."""
    import vv_log_additions as additions
    import vv_log_tools as tools
    from vv_lost_titles import PREFERENCES
    words = {w: k for k, w in enumerate(PREFERENCES[game])}
    male, female = SEX_VALUES[game]
    found: dict[tuple, Departed] = {}
    for b in additions.person_blocks(folder, slot, game):
        if not (b.heading.startswith("Death ") or b.heading.startswith("Disappeared")):
            continue
        name, head, body = b.identity
        sex = {"Male": male, "Female": female}.get(b.value("Sex") or "")
        age = b.value("Age at death") or b.value("Age")
        if not name or head is None or body is None or sex is None or not age or not age.lstrip("-").isdigit():
            continue
        prefs = []
        for label in ("Likes", "Dislikes"):
            value = b.value(label)
            if value is None:
                prefs.append(None)
                continue
            ws = tools.preference_words(value)
            prefs.append(tuple(sorted(words[w] for w in ws)) if all(w in words for w in ws) else None)
        father = (b.value("Father", "    ") or "").strip()
        mother = (b.value("Mother", "    ") or "").strip()
        person = Departed(name, sex, int(age), head, body, prefs[0], prefs[1],
                          "" if father == "(none)" else father, "" if mother == "(none)" else mother, b.heading)
        found[(name, sex, head, body, person.likes, person.dislikes)] = person   # the newest record wins
    return list(found.values())


def _is(person: Departed, s: Snapshot, exact_age: bool) -> bool:
    name, sex, head, body, likes, dislikes = s.identity()
    age = s.age()
    if (name, sex, head, body) != (person.name, person.sex, person.head, person.body) or age is None:
        return False
    if (age != person.age) if exact_age else (age > person.age):
        return False
    if person.likes is not None and likes != person.likes:
        return False
    if person.dislikes is not None and dislikes != person.dislikes:
        return False
    father, mother = s.parents()
    return (not person.father or not father or father == person.father) and \
        (not person.mother or not mother or mother == person.mother)


# ---------------------------------------------------------------------------------------------------
# The backfill
# ---------------------------------------------------------------------------------------------------

@dataclass
class Result:
    path: Path
    written: bool
    made: list[str] = field(default_factory=list)      # "<name>: <source>"
    not_found: list[str] = field(default_factory=list)  # departed with no source
    unsure: list[str] = field(default_factory=list)     # two different entries could be them
    note: str = ""


def _keep(game: int, data: bytes) -> bytes:
    """The persistent bytes (VV_RS_KEEP_*) of a snapshot's data, to tell two entries apart."""
    keep = {1: ((0x350, 4), (0x360, 0x2C), (0x398, 0x20), (0x3BC, 0x18)),
            2: ((0x538, 4), (0x548, 0x10), (0x564, 0x5C), (0x5F0, 0x1F0), (0x7E4, 0x19)),
            3: ((0xDC8, 0x74), (0xEAC, 0x18), (0xFB4, 0x0C), (0xFC0, 0x0C)),
            4: ((0x1B90, 0x74), (0x1C5C, 0x18), (0x1E60, 0x18)),
            5: ((0x1B90, 0x74), (0x1C5C, 0x1C), (0x1CED, 0x07), (0x1CFC, 0x04), (0x1F5C, 0x18))}[game]
    return b"".join(data_at(game, data, o, n) for o, n in keep)


def plan(folder: Path, game: int, slot: int) -> tuple[list[Snapshot], Result]:
    """What a backfill would add (reads only)."""
    target = path(folder, game, slot)
    result = Result(target, False)
    existing: list[Snapshot] = []
    if target.is_file():
        parsed = parse(target.read_bytes(), game)
        if parsed is None:
            result.note = "the Revive Snapshots file is not one this version reads; it was left as it is"
            return [], result
        existing = parsed
    people = departed(folder, game, slot)
    srcs = sources(folder, game, slot)
    used: set[tuple[int, int]] = set()
    added: list[Snapshot] = []
    for person in people:
        if any(_is(person, s, s.source == CAPTURED) for s in existing):
            continue                    # already kept (a capture, or an earlier backfill): never again
        best: tuple | None = None       # (age, source index, entry index, snapshot)
        unsure = False
        for si, src in enumerate(srcs):
            for ei, d in enumerate(src.entries):
                if (si, ei) in used:
                    continue
                s = Snapshot(game, d, src.kind, EXACT_IDENTITY, src.when)
                if not _is(person, s, False):
                    continue
                age = s.age() or 0
                if best is None or age > best[0]:
                    best, unsure = (age, si, ei, s), False
                elif age == best[0] and _keep(game, d) != _keep(game, best[3].data):
                    unsure = True
        if best is None:
            result.not_found.append(person.name)
            continue
        if unsure:
            result.unsure.append(person.name)
            continue
        age, si, ei, s = best
        used.add((si, ei))
        if age == person.age:
            s.exact |= EXACT_LATER      # a body's copy: everything as at the end
        added.append(s)
        result.made.append(f"{person.name}: {srcs[si].label}")
    return existing + added, result if added else result


def backfill(folder: Path, game: int, slot: int) -> Result:
    """Add the snapshots `plan` finds to the slot's Revive Snapshots file.  Idempotent; never a save."""
    snapshots, result = plan(folder, game, slot)
    if not result.made:
        return result
    if len(snapshots) > MAX_ENTRIES:
        snapshots = snapshots[-MAX_ENTRIES:]
    _write(result.path, build(game, snapshots))
    result.written = True
    return result
