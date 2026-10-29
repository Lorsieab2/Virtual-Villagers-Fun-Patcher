"""The original looks behind Change Appearance's "Reset to original": the patcher's side (all five games).

The owner (2026-10-28): Change Appearance and Change Appearance for All get a "Reset to original" button
that puts a villager back to the head, body and mask they had before any Change Appearance or island event
changed them.  "VVFP Original Look.dll" (native/vvfp_original_look) keeps those originals in the save's own
file, recording each villager the first time it sees them.  A villager changed BEFORE that DLL existed
would be recorded with the changed look -- so Repair Saves & Logs (src/vv_log_tools.py approve_repair,
with the game closed) adds what the patcher's logs prove, here.

THE FILE is the DLL's (native/vvfp_original_look/original_look_store.inc says it all):
"Virtual Villagers Fun Patcher\\Save <S>\\Data\\Original Looks\\Original Looks - Save <S>.dat", routed like
every per-save data file (src/vv_save_layout.py).  This module writes only its "logged" part -- one entry
per living villager the logs say something about, keyed by the DLL's identity of the villager (name, sex
and the parents' names; A New Home: name, sex and family) -- and keeps every record entry byte for byte.
A file that is not valid is never written over (the DLL sets it aside at its next load).

THE RULES (never guess):
  * A villager's original head and body are the Old head and Old body of the EARLIEST "Appearance changed"
    record of them (the Births and Conceptions log: Change Appearance's and an island event's changes
    alike), found by following their records back from the look they have in the save -- each record's New
    head and body must be the look the next one starts from, under one of their names (a "Name changed"
    record, an island event's rename or a rename the patcher made gives the older names).
  * The mask is the one they had before that first logged change: that record's own "Old mask" line (every
    "Appearance changed" record carries the mask before and after since 2026-10-28, a change of the mask
    alone too: native/shared/appearance_log.h); for an older record, the "old" side of their earliest
    island event "Mask:" step when there is one, otherwise the "Mask:" line of their own Birth, Arrived or
    island event newcomer record (no line: no mask).  No such record: the mask is not known.
  * THE GAME'S OWN CHANGES ARE KEPT (the owner, 2026-10-28): The Secret City's Tribal Chief wears the robe
    the game gave (body 29, the chief flag +0xE80 set: the robing 0x45FBC0, which no log records), so a
    robed chief's records are followed by the head alone and their original body is the robe.  The
    clothing dialog's outfits (The Lost Children to New Believers) are not in any log either; a villager
    whose body it changed reads as "changed with no record" below, so not known.
  * NOT KNOWN, recorded as such so the DLL never records a first sight for them either: the mask cannot be
    told (and in New Believers any mask the logs name, which may be a Heathen's own); or the looks of their
    own Birth / Arrived / newcomer record are not where their records start (they were seen changed with no
    record of it); or an island event changed their head or body with no "Appearance changed" record of it
    (Island Events logs older than that record); or a record of their (unique) name changed a look that is
    not on their chain; or one record is on two living villagers' chains.
  * No record and no sign of a change: nothing -- the DLL's first sight is right for them.
  * Two living villagers of one identity: nothing for either.
Running it again changes nothing (the same logs give the same part, and an unchanged file is not written).
"""
from __future__ import annotations

import os
import re
import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path

import vv_save_layout as layout

DATA = "Virtual Villagers Fun Patcher Data"
RELATIVE = DATA + r"\Original Looks\Original Looks - Save {slot}.dat"
MAGIC = 0x314C4F56                  # 'VOL1'
VERSION = 1
HEADER = 24
ENTRY = 20
LOGGED_ENTRY = 16
LOGGED_MAX = 256
COUNTS = (150, 256)
FIRST_RUN, SEEN, LOGS = 1, 2, 3
KNOWN, UNKNOWN = 1, 2
MASKS = {"none": 0, "": 0, "blue mask": 1, "orange mask": 2, "red mask": 3, "purple mask": 4,
         "tribal chief mask": 5}
# The record fields the identity is made of, relative to the name in a saved entry (src/vv_last_names.py
# FIELDS) -- the same bytes the DLL reads from the record in memory (original_look_records.inc LAYOUT).
NAME_BYTES = {1: 0x1C, 2: 0x18, 3: 0x19, 4: 0x19, 5: 0x19}
PARENT_BYTES = 0x19
VV3_CHIEF_FROM_NAME = 0xAC
ROBE_BODY = 29
_LOG_NUMBER = re.compile(r" Log (\d+)\.txt$", re.I)


class OriginalLookError(Exception):
    """Nothing was written; the message says why."""


# ---------------------------------------------------------------------------------------------------
# The file
# ---------------------------------------------------------------------------------------------------

@dataclass
class Entry:
    roster: int = 0
    id: int = 0
    head: int = 0
    body: int = 0
    mask: int = 0
    source: int = 0
    game_body: int = 0       # 1: the game itself set the body since (the DLL's ol_game_body); kept as it is


@dataclass
class Logged:
    id: int
    head: int
    body: int
    mask: int
    kind: int


@dataclass
class OriginalLooks:
    game: int
    entries: list[Entry]
    logged: list[Logged] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.entries)


def path(folder: Path, slot: int) -> Path:
    """Where the slot's file is (present or not)."""
    if slot not in (1, 2, 3, 4, 5):
        raise OriginalLookError(f"There is no save slot {slot}.")
    return layout.route(Path(folder), RELATIVE.format(slot=slot))


def parse(data: bytes, game: int) -> OriginalLooks | None:
    """The file, or None when the DLL would not read it (it sets such a file aside)."""
    if len(data) < HEADER + 4:
        return None
    magic, version, file_game, count, logged, zero = struct.unpack_from("<6I", data)
    if (magic != MAGIC or version != VERSION or file_game != game or count not in COUNTS or logged > LOGGED_MAX
            or zero != 0 or len(data) != HEADER + count * ENTRY + logged * LOGGED_ENTRY + 4
            or struct.unpack_from("<I", data, len(data) - 4)[0] != zlib.crc32(data[:-4])):
        return None
    entries = []
    for i in range(count):
        roster, ident, head, body, mask, source, game_body = struct.unpack_from("<IIiiBBB", data, HEADER + i * ENTRY)
        entries.append(Entry(roster, ident, head, body, mask, source, game_body))
    at = HEADER + count * ENTRY
    kept = []
    for i in range(logged):
        ident, head, body, mask, kind = struct.unpack_from("<IiiBB", data, at + i * LOGGED_ENTRY)
        kept.append(Logged(ident, head, body, mask, kind))
    return OriginalLooks(game, entries, kept)


def build(looks: OriginalLooks) -> bytes:
    """The file's bytes (the DLL's ol_publish, the same layout)."""
    if looks.count not in COUNTS or len(looks.logged) > LOGGED_MAX:
        raise OriginalLookError("The original looks do not fit the file.")
    out = bytearray(struct.pack("<6I", MAGIC, VERSION, looks.game, looks.count, len(looks.logged), 0))
    for e in looks.entries:
        out += struct.pack("<IIiiBBBB", e.roster, e.id, e.head, e.body, e.mask, e.source, e.game_body, 0)
    for e in looks.logged:
        out += struct.pack("<IiiBBBB", e.id, e.head, e.body, e.mask, e.kind, 0, 0)
    out += struct.pack("<I", zlib.crc32(bytes(out)))
    return bytes(out)


def _write(target: Path, data: bytes) -> None:
    """Through "<name>.tmp", flushed, then moved over the file: never half a file."""
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
# Who is who: the DLL's identity, from the save
# ---------------------------------------------------------------------------------------------------

_FNV = 16777619
_MASK32 = 0xFFFFFFFF


def _text(h: int, raw: bytes, capacity: int) -> int:
    for byte in raw[:capacity]:
        if byte == 0:
            break
        h = ((h ^ byte) * _FNV) & _MASK32
    return h


def _dword(h: int, raw: bytes) -> int:
    for byte in raw[:4]:
        h = ((h ^ byte) * _FNV) & _MASK32
    return h


def identity(game: int, name: bytes, sex: bytes, father: bytes = b"", mother: bytes = b"",
             family: bytes = b"\0\0\0\0") -> tuple[int, int]:
    """(identity, stable part) as the DLL makes them (original_look_records.inc ol_identity / ol_stable):
    `sex` and `family` the record's raw dwords, the names their raw bytes."""
    h = _dword(2166136261, sex)
    if game == 1:
        h = _dword(h, family)
    else:
        h = _text(h, father, PARENT_BYTES)
        h = ((h ^ 0xFE) * _FNV) & _MASK32
        h = _text(h, mother, PARENT_BYTES)
        h = ((h ^ 0xFD) * _FNV) & _MASK32
    stable = h or 1
    h = _text(2166136261, name, NAME_BYTES[game])
    h = ((h ^ 0xFF) * _FNV) & _MASK32
    h = ((h ^ stable) * _FNV) & _MASK32
    return h or 1, stable


@dataclass
class Living:
    """One living villager of the save."""
    seen: object                            # src/vv_reconcile.py Seen
    id: int
    robed: bool = False                     # The Secret City's Tribal Chief in the robe the game gave them


def living(folder: Path, game: int, slot: int) -> list[Living]:
    """The save's living villagers, each with the DLL's identity."""
    import vv_last_names as ln
    import vv_reconcile as rc
    save = Path(folder) / f"{rc._checker().SAVE_STEMS[game]}{slot}.ldw"
    data = save.read_bytes()
    alive, _bodies = rc.read_save(save, game)
    f = ln.FIELDS[game]
    out = []
    for s in alive:
        at = s.at
        name = data[at:at + NAME_BYTES[game]]
        sex = data[at + f.sex:at + f.sex + 4]
        if game == 1:
            ident, _ = identity(1, name, sex, family=data[at + f.family:at + f.family + 4])
        else:
            ident, _ = identity(game, name, sex, data[at + f.father:at + f.father + PARENT_BYTES],
                                data[at + f.mother:at + f.mother + PARENT_BYTES])
        # The Secret City's chief flag +0xE80 (the robing 0x45FBC0 is its only writer), saved in the
        # record's second window, 0xAC after the name; the robe is body 29 (0x45FBDE).
        robed = game == 3 and data[at + VV3_CHIEF_FROM_NAME] != 0 and s.body == ROBE_BODY
        out.append(Living(s, ident, robed))
    return out


# ---------------------------------------------------------------------------------------------------
# What the logs say
# ---------------------------------------------------------------------------------------------------

@dataclass
class Change:
    name: str
    old: tuple
    new: tuple
    old_mask: int | None = None             # "Old mask" / "New mask" (since 2026-10-28; None: not recorded)
    new_mask: int | None = None


@dataclass
class Evidence:
    changes: list[Change] = field(default_factory=list)            # "Appearance changed", oldest first
    masks: list[tuple[str, int | None, int | None]] = field(default_factory=list)   # (name, old, new), oldest first
    looks: list[tuple[str, str, int | None, int | None]] = field(default_factory=list)   # island event (name, "Head"/"Body", old, new)
    renames: list[tuple[str, str]] = field(default_factory=list)   # (old name, new name)
    own: list[tuple[str, str | None, tuple, int]] = field(default_factory=list)    # (name, sex, looks, mask)
    names: set[str] = field(default_factory=set)                   # every villager name the logs know


def _mask(value: str | None) -> int | None:
    if value is None:
        return 0
    return MASKS.get(value.strip().lower())


def _int(value: str | None) -> int | None:
    try:
        return int(str(value).strip().split()[0])
    except (ValueError, IndexError, AttributeError):
        return None


def _in_order(paths: list[Path]) -> list[Path]:
    """A numbered log's files oldest first: the older shared folders, then the save's own; by number."""
    def key(p: Path) -> tuple:
        m = _LOG_NUMBER.search(p.name)
        return (layout.is_slot_folder(p) or 0, str(p.parent), int(m.group(1)) if m else 0, p.name)
    return sorted(paths, key=key)


def _sub_lines(lines: list[str], label: str) -> dict[str, str] | None:
    """A Birth record's "  Child:" with the lines indented under it."""
    for k, line in enumerate(lines):
        if line.startswith(f"  {label}:"):
            values = {"Name": line.split(":", 1)[1].strip()}
            for sub in lines[k + 1:]:
                if not sub.startswith("    "):
                    break
                if ":" in sub:
                    key, value = sub.strip().split(":", 1)
                    values.setdefault(key, value.strip())
            return values
    return None


def evidence(folder: Path, game: int, slot: int) -> Evidence:
    """Every record of the slot's village that says how a villager looked, oldest first."""
    import vv_log_additions as additions
    import vv_log_decisions as decisions
    import vv_reconcile as rc
    folder = Path(folder)
    villages = additions.current_villages(folder, game, slot)
    checker = rc._checker()
    out = Evidence()
    files = checker.log_files(folder)
    births = _in_order([p for p in files if "Births and Conceptions" in p.name])
    events = _in_order([p for p in files if "Island Events" in p.name])
    deaths = [p for p in files if "Deaths" in p.name or "Unaccounted" in p.name]
    for p in births:
        for b in additions.blocks(p):
            if not b.of(slot, game, villages):
                continue
            head = b.heading
            if head == "Appearance changed":
                old = (_int(b.value("Old head")), _int(b.value("Old body")))
                new = (_int(b.value("New head")), _int(b.value("New body")))
                name = b.value("Name") or ""
                if None not in old + new and name:
                    masked = b.value("Old mask") is not None and b.value("New mask") is not None
                    out.changes.append(Change(name, old, new, _mask(b.value("Old mask")) if masked else None,
                                              _mask(b.value("New mask")) if masked else None))
                    out.names.add(name)
            elif head == "Name changed":
                if b.value("Old name") and b.value("Name"):
                    out.renames.append((b.value("Old name"), b.value("Name")))
            elif rc.BIRTH.match(head):
                child = _sub_lines(b.lines, "Child")
                if child and child["Name"] and not child["Name"].startswith("("):
                    out.own.append((child["Name"], child.get("Sex"), (_int(child.get("Head")), _int(child.get("Body"))),
                                    _mask(child.get("Mask"))))
                    out.names.add(child["Name"])
            elif rc.ARRIVED.match(head):
                name = b.value("Name") or ""
                if name:
                    out.own.append((name, b.value("Sex"), (b.int_value("Head"), b.int_value("Body")),
                                    _mask(b.value("Mask"))))
                    out.names.add(name)
    for p in events:
        for b in additions.blocks(p):
            if not b.of(slot, game, villages) or not rc.EVENT.match(b.heading):
                continue
            name = b.value("Name") or ""
            renamed = rc.CHANGE.match(name)
            if renamed:
                out.renames.append((renamed.group(1), renamed.group(2)))
                name = renamed.group(2)
            if not name:
                continue
            out.names.add(name)
            if (b.value("New villager") or "").lower().startswith("yes"):
                out.own.append((name, b.value("Sex"), (b.int_value("Head"), b.int_value("Body")), _mask(b.value("Mask"))))
            for line in b.lines[1:]:
                m = re.match(r"^  (Mask|Head|Body): (.*?) -> (.*?)\s*$", line)
                if m and m.group(1) == "Mask":
                    out.masks.append((name, _mask(m.group(2)), _mask(m.group(3))))
                elif m:
                    out.looks.append((name, m.group(1), _int(m.group(2)), _int(m.group(3))))
    for p in deaths:
        for b in additions.blocks(p):
            if b.of(slot, game, villages) and b.value("Name"):
                out.names.add(b.value("Name"))
    # The renames the patcher itself made (Last Names, Number Duplicate Names, a name given back...).
    for d in decisions.load(folder, game, slot):
        if d.get("kind") == decisions.ALIAS_KIND and isinstance(d.get("name"), str) \
                and isinstance(d.get("field"), str) \
                and (villages is None or d.get("village") is None or d.get("village") in villages):
            out.renames.append((d["name"], d["field"]))
    return out


def _names(name: str, renames: list[tuple[str, str]]) -> set[str]:
    """Every name a villager called `name` now has had, by the recorded renames."""
    names, todo = {name}, [name]
    while todo:
        now = todo.pop()
        for old, new in renames:
            if new == now and old not in names:
                names.add(old)
                todo.append(old)
    return names


@dataclass
class Found:
    """What the logs say of one living villager."""
    kind: int | None                       # KNOWN, UNKNOWN, or None: nothing to say
    head: int = 0
    body: int = 0
    mask: int = 0
    why: str = ""
    chain: tuple = ()                      # the indices of the Appearance changed records followed


def find(v: Living, ev: Evidence, others: set[str] = frozenset(), game: int = 0) -> Found:
    """The original look the logs prove for one villager (see THE RULES); `others` are the names of the
    other living villagers."""
    s = v.seen
    names = _names(s.name, ev.renames)
    # The game's own change is kept (the owner, 2026-10-28): a Secret City chief's robe was given by the game
    # with no record, so their records are followed by the head alone and the original body is the robe.
    def same(a: tuple, b: tuple) -> bool:
        return a[0] == b[0] if v.robed else a == b
    state = (s.head, s.body)
    chain = []
    for k in range(len(ev.changes) - 1, -1, -1):
        c = ev.changes[k]
        if c.name in names and same(c.new, state):
            chain.append(k)
            state = c.old
    chain.reverse()
    if v.robed:
        state = (state[0], ROBE_BODY)
    unique_name = not (names & set(others)) and not _shared_name(ev, names)
    off_chain = [k for k, c in enumerate(ev.changes) if c.name in names and k not in chain]
    # An island event's head or body step with no "Appearance changed" record of it (one written before
    # island events wrote both): a change the chain cannot place.
    unplaced = [step for step in ev.looks if step[0] in names and not any(
        c.name == step[0] and (c.old[0], c.new[0]) == (step[2], step[3]) if step[1] == "Head"
        else c.name == step[0] and (c.old[1], c.new[1]) == (step[2], step[3]) for c in ev.changes)]
    own = [o for o in ev.own if o[0] in names
           and (o[1] is None or s.sex is None or o[1].strip().lower() == str(s.sex).strip().lower())]
    record_looks = own[0][2] if len(own) == 1 and None not in own[0][2] else None
    if record_looks is not None and not same(record_looks, state):
        return Found(UNKNOWN, why="their own record's looks are not where their changes start: changed with no "
                                  "record of it")
    if unplaced and unique_name:
        return Found(UNKNOWN, why="an island event changed their look with no Appearance changed record of it")
    # A logged change that does not lead to the look they have now (Codex, PR #653): checked before "no
    # chain", or a villager whose only change is off the way would read as never changed.
    if off_chain and unique_name:
        return Found(UNKNOWN, why="a record of their name changed a look that is not on their way")
    if not chain:
        return Found(None)
    first = ev.changes[chain[0]]
    masks = [m for m in ev.masks if m[0] in names]
    if first.old_mask is not None:
        # The earliest change's own "Old mask": Change Appearance's mask store, whatever the game.
        return Found(KNOWN, state[0], state[1], first.old_mask, chain=tuple(chain))
    if masks and masks[0][1] is not None:
        mask = masks[0][1]
    elif len(own) == 1 and own[0][3] is not None:
        mask = own[0][3]
    else:
        return Found(UNKNOWN, why="the mask before their first change is not recorded")
    if game == 5 and mask != 0:
        # New Believers' logs name a Heathen's own mask (the game's, from the faction) and the patcher's
        # cosmetic one alike (native/shared/mask_line.h): which one this was cannot be told.
        return Found(UNKNOWN, why="New Believers' logs do not tell a Heathen's own mask from a cosmetic one")
    return Found(KNOWN, state[0], state[1], mask, chain=tuple(chain))


def _shared_name(ev: Evidence, names: set[str]) -> bool:
    """Whether the logs know another villager of one of these names: more than one Birth / Arrived /
    newcomer record of it."""
    return any(sum(1 for o in ev.own if o[0] == n) > 1 for n in names)


@dataclass
class Result:
    path: Path
    written: bool
    known: int = 0
    unknown: int = 0
    note: str = ""


def backfill(folder: Path, game: int, slot: int) -> Result:
    """Add the logs' originals of the slot's village to its file (see THE RULES).  Call it only with the
    game closed (Repair Saves & Logs).  Never writes over a file that is not valid."""
    folder = Path(folder)
    target = path(folder, slot)
    looks = None
    if target.is_file():
        looks = parse(target.read_bytes(), game)
        if looks is None:
            return Result(target, False, note=f"{target.name} could not be read; the game sets it aside and starts "
                                              "a new one, and the next Repair Saves & Logs adds the logs' originals")
    people = living(folder, game, slot)
    ev = evidence(folder, game, slot)
    holders: dict[int, int] = {}
    for v in people:
        holders[v.id] = holders.get(v.id, 0) + 1
    found = {v.id: find(v, ev, {o.seen.name for o in people if o is not v}, game)
             for v in people if holders[v.id] == 1}
    claims: dict[int, list[int]] = {}
    for ident, f in found.items():
        for k in f.chain:
            claims.setdefault(k, []).append(ident)
    for ks in claims.values():
        if len(ks) > 1:
            for ident in ks:
                found[ident] = Found(UNKNOWN, why="one record is on two villagers' way")
    logged = [Logged(ident, f.head, f.body, f.mask, f.kind) for ident, f in found.items() if f.kind is not None]
    logged = logged[:LOGGED_MAX]
    known = sum(1 for e in logged if e.kind == KNOWN)
    if looks is None:
        if not logged:
            return Result(target, False, note="nothing in the logs to add")
        count = 256 if game in (1, 2) or any((v.seen.record or 0) >= 150 for v in people) else 150
        entries = [Entry() for _ in range(count)]
        for v in people:
            if v.seen.record is not None and 0 <= v.seen.record < count and holders[v.id] == 1:
                entries[v.seen.record].roster = v.id
        looks = OriginalLooks(game, entries)
    before = build(looks)
    looks.logged = logged
    after = build(looks)
    if target.is_file() and after == before:
        return Result(target, False, known, len(logged) - known, "already up to date")
    _write(target, after)
    return Result(target, True, known, len(logged) - known)
