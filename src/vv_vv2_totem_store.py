"""The Lost Children: the Esteemed Elders' totems kept OUT of the 256 villager records.

The owner (2026-10-19): totems are movable decorations that no longer take a villager record.  The
companion "VVFP VV2 Totems.dll" (native/vvfp_vv2_totems) keeps every totem in a store of its own,
saved for each save in

    <save folder>\\Virtual Villagers Fun Patcher\\Save <N>\\Data\\Elder Totems\\ElderTotems.dat

and moves every statue the save holds into it when the village loads.  This module reads and writes
the same file for Repair Saves & Logs:

  * "Move Totems Out of the Save" -- the same move, done with the game closed.
  * "Put Totems Back Into the Save" -- before removing the patch: each totem in the file is written
    back into the save the way the game itself keeps a totem (one saved villager entry), as many as
    the free villager records allow; the rest stay in the file, and the player is told.
  * "Change Totem Colour" -- one of the eight faces of the game's own totems.png for an elder's totem.
  * the village's "give Esteemed Elders their totems automatically" setting.

THE FILE (native/vvfp_vv2_totems/vvfp_vv2_totems.c writes the same): "VVFP VV2 TOTEMS\\0", then
version 1, game 2, slot, entry size 0x2E0, roster count R and totem count T (little-endian 32-bit),
R roster rows (the name in 24 bytes, head, body, sex) -- the village the file belongs to -- then T
totems, each exactly the 0x2E0-byte entry the game saves for a totem record, then the FNV-1a hash of
all of it.  The file belongs to a save when more than half of its roster stands in that save.

Safety, as every Repair Saves & Logs write: refused while the game runs; the save folder is backed up
first; a copy of every file changed is kept in Copies Made Before Repairs; every file is written
through a temporary file, read back, and put back on any failure; one "Repair <n>" record in the
Repairs Made log names every change.  A totem is never lost: a file gains totems before the save
loses them, and the save gains them before the file loses them, so a failure between the two leaves
a totem in both -- which the companion and these tools count once (`same_statue`).
"""
from __future__ import annotations

import os
import struct
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import vv_last_names as ln
import vv_log_tools as tools
import vv_save_backup
import vv_save_layout as layout
import vv_vv2_totems as totems

GAME = 2
MAGIC = b"VVFP VV2 TOTEMS\0"
VERSION = 1
ENTRY = 0x2E0
HEADER = 40
ROSTER_ROW = 36
MAX_TOTEMS = 100000
KIND = "Elder Totems"
FILE_NAME = "ElderTotems.dat"
SETTINGS_NAME = "Elder Totem Settings.dat"
SETTINGS_HEADER = "VVFP VV2 ELDER TOTEM SETTINGS v1"

LABEL_MOVE = "Move Totems Out of the Save"
LABEL_PUT_BACK = "Put Totems Back Into the Save"
LABEL_COLOUR = "Change Totem Colour"
LABEL_AUTO = "Give Esteemed Elders their totems automatically"
DLL = "VVFP VV2 Totems.dll"
FEATURE_ID = "vv2_totems_out_of_entries"

BACKUP_MOVE = "(before moving totems out of the save)"
BACKUP_PUT_BACK = "(before putting totems back into the save)"
BACKUP_COLOUR = "(before changing a totem colour)"

# Offsets inside a saved entry (record offset - 0x524).
E_HEALTH, E_SEX, E_HEAD, E_BODY, E_TYPE, E_LINEAGE = 0x08, 0x14, 0x24, 0x28, 0x2C, 0x30
E_IS_TOTEM, E_X, E_Y, E_NAME, E_FATHER, E_MOTHER, E_FLAG = 0x34, 0x38, 0x3C, 0x40, 0x59, 0x72, 0x2DC
NAME_CAP, PARENT_CAP = 0x18, 0x19


class StoreError(Exception):
    """Nothing was changed (or every file was put back); the message says why."""


def _fnv1a(data: bytes) -> int:
    h = 2166136261
    for b in data:
        h = ((h ^ b) * 16777619) & 0xFFFFFFFF
    return h


def _text(data: bytes, at: int, cap: int) -> str:
    return bytes(data[at:at + cap]).split(b"\0", 1)[0].decode("latin-1")


def _i32(data: bytes, at: int) -> int:
    return struct.unpack_from("<i", data, at)[0]


# ---------------------------------------------------------------------------
# The file
# ---------------------------------------------------------------------------

def store_path(folder: Path, slot: int) -> Path:
    """The save's own file: "<save folder>\\Virtual Villagers Fun Patcher\\Save <N>\\Data\\Elder Totems\\
    ElderTotems.dat" -- a new file, so never in the older layout."""
    if int(slot) not in layout.SLOTS:
        raise StoreError(f"Save {slot} is not a save slot (1 to 5).")
    return Path(folder) / layout.save_root(slot) / layout.SAVE_DATA / KIND / FILE_NAME


def settings_path(folder: Path, slot: int) -> Path:
    return store_path(folder, slot).with_name(SETTINGS_NAME)


@dataclass
class Totem:
    entry: bytes                    # the 0x2E0-byte saved entry

    @property
    def name(self) -> str:
        return _text(self.entry, E_NAME, NAME_CAP)

    @property
    def sex(self) -> int:
        return _i32(self.entry, E_SEX)

    @property
    def head(self) -> int:
        return _i32(self.entry, E_HEAD)

    @property
    def body(self) -> int:
        return _i32(self.entry, E_BODY)

    @property
    def lineage(self) -> int:
        return _i32(self.entry, E_LINEAGE)

    @property
    def type(self) -> int:
        return _i32(self.entry, E_TYPE)

    @property
    def face(self) -> int:
        return int(self.type % 8) if self.type >= 0 else -((-self.type) % 8)

    @property
    def x(self) -> int:
        return _i32(self.entry, E_X)

    @property
    def y(self) -> int:
        return _i32(self.entry, E_Y)

    @property
    def father(self) -> str:
        return _text(self.entry, E_FATHER, PARENT_CAP)

    @property
    def mother(self) -> str:
        return _text(self.entry, E_MOTHER, PARENT_CAP)

    @property
    def key(self) -> str:
        return f"{self.name}|{self.sex}|{self.head}|{self.body}|{self.lineage}|{self.father}|{self.mother}|{self.type}"

    def label(self) -> str:
        return f"{self.name}'s totem ({totems.face(self.type)}, head {self.head}, body {self.body})"


def same_statue(a: bytes, b: bytes) -> bool:
    """What 0x44D190 copies that tells one statue from another (the companion's same_statue)."""
    return (_text(a, E_NAME, NAME_CAP), _i32(a, E_SEX), _i32(a, E_HEAD), _i32(a, E_BODY), _i32(a, E_LINEAGE),
            _i32(a, E_TYPE), _text(a, E_FATHER, PARENT_CAP), _text(a, E_MOTHER, PARENT_CAP)) == \
           (_text(b, E_NAME, NAME_CAP), _i32(b, E_SEX), _i32(b, E_HEAD), _i32(b, E_BODY), _i32(b, E_LINEAGE),
            _i32(b, E_TYPE), _text(b, E_FATHER, PARENT_CAP), _text(b, E_MOTHER, PARENT_CAP))


@dataclass
class Store:
    slot: int
    roster: list[tuple[str, int, int, int]] = field(default_factory=list)   # name, head, body, sex
    totems: list[Totem] = field(default_factory=list)

    def has(self, entry: bytes) -> bool:
        return any(same_statue(t.entry, entry) for t in self.totems)


def parse(data: bytes) -> Store:
    if len(data) < HEADER + 4 or data[:16] != MAGIC:
        raise StoreError("not an ElderTotems.dat file")
    version, game, slot, size, rows, count = struct.unpack_from("<6I", data, 16)
    if version != VERSION or game != GAME or size != ENTRY:
        raise StoreError(f"an ElderTotems.dat this patcher does not know (version {version}, game {game})")
    if rows > 256 or count > MAX_TOTEMS or HEADER + rows * ROSTER_ROW + count * ENTRY + 4 != len(data):
        raise StoreError("ElderTotems.dat is not whole")
    if struct.unpack_from("<I", data, len(data) - 4)[0] != _fnv1a(data[:-4]):
        raise StoreError("ElderTotems.dat does not match its own check")
    roster = []
    at = HEADER
    for _ in range(rows):
        roster.append((_text(data, at, NAME_CAP), _i32(data, at + 24), _i32(data, at + 28), _i32(data, at + 32)))
        at += ROSTER_ROW
    out = []
    for _ in range(count):
        out.append(Totem(bytes(data[at:at + ENTRY])))
        at += ENTRY
    return Store(slot, roster, out)


def serialize(store: Store) -> bytes:
    body = bytearray(MAGIC)
    body += struct.pack("<6I", VERSION, GAME, store.slot, ENTRY, len(store.roster), len(store.totems))
    for name, head, body_no, sex in store.roster:
        raw = name.encode("latin-1", "replace")[:NAME_CAP - 1]
        body += raw + bytes(24 - len(raw)) + struct.pack("<iii", head, body_no, sex)
    for t in store.totems:
        if len(t.entry) != ENTRY:
            raise StoreError("a totem entry is not 0x2E0 bytes")
        body += t.entry
    body += struct.pack("<I", _fnv1a(bytes(body)))
    return bytes(body)


def read(folder: Path, slot: int) -> Store | None:
    """The slot's file, or None when there is none."""
    path = store_path(folder, slot)
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise StoreError(f"{path.name} could not be read ({exc}).") from exc
    store = parse(data)
    store.slot = int(slot)
    return store


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        with open(temporary, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise
    if path.read_bytes() != data:
        raise StoreError(f"{path.name} did not read back as written.")


# ---------------------------------------------------------------------------
# The save's side
# ---------------------------------------------------------------------------

def _offsets(data: bytes) -> list[int]:
    return totems._offsets(data)


def roster_of(data: bytes, offsets: list[int]) -> list[tuple[str, int, int, int]]:
    return [(_text(data, at, NAME_CAP), _i32(data, at + totems.HEAD), _i32(data, at + totems.BODY),
             _i32(data, at + totems.SEX)) for at in offsets if data[at + totems.IS_TOTEM] == 0]


def bound(store: Store, data: bytes) -> bool:
    """More than half of the file's roster stands in the save (the companion's bound_to)."""
    if not store.roster:
        return not store.totems
    living = set(roster_of(data, _offsets(data)))
    return sum(1 for row in store.roster if row in living) * 2 > len(store.roster)


def _entry_at(data: bytes, at: int) -> bytes:
    return bytes(data[at + totems.ENTRY:at + totems.ENTRY + ENTRY])


def statues_in_save(data: bytes) -> list[tuple[int, int]]:
    """(place among the loaded entries, name offset) of every statue: totem mark set, health 0 or less.
    A living villager carrying the mark is never one (Fix Rare Villager Turning Into Totem's case)."""
    return [(k, at) for k, at in enumerate(_offsets(data))
            if data[at + totems.IS_TOTEM] != 0 and _i32(data, at + totems.HEALTH) <= 0]


def _without(data: bytes, offsets: list[int], drop: set[int]) -> bytes:
    """The save with the entries at those places removed, the rest closed up in order -- exactly what
    the game's own packer 0x44B580 writes when those records are no longer in use."""
    if not offsets:
        return bytes(data)
    first = offsets[0] + totems.ENTRY
    kept = [_entry_at(data, at) for k, at in enumerate(offsets) if k not in drop]
    out = bytearray(data)
    for k, entry in enumerate(kept):
        out[first + k * ENTRY:first + (k + 1) * ENTRY] = entry
    # The entries the move freed, after the last kept one, are cleared: the game's loader stops at the
    # first entry not flagged in use (0x44B6F5) and never reads them, and nothing reading the save can
    # take a moved statue's old bytes for a villager.
    tail = first + len(kept) * ENTRY
    out[tail:min(len(out), first + len(offsets) * ENTRY)] = bytes(max(0, min(len(out), first + len(offsets) * ENTRY) - tail))
    return bytes(out)


def _with(data: bytes, offsets: list[int], entries: list[bytes]) -> bytes:
    """The save with `entries` added after the last loaded one (vv_vv2_totems.give_totems' way)."""
    first = offsets[0] + totems.ENTRY
    out = bytearray(data)
    n = len(offsets)
    for entry in entries:
        at = first + n * ENTRY
        if at + ENTRY > len(out):
            raise StoreError("The save is shorter than its villager table; nothing was changed.")
        out[at:at + ENTRY] = entry
        n += 1
    end = first + n * ENTRY + E_FLAG
    if end < len(out):
        out[end] = 0
    return bytes(out)


def _record(folder: Path, data: bytes, slot: int, now: datetime | None, lines: list[str]) -> None:
    try:
        totems._record(folder, totems._village(data, slot), slot, now, lines)
    except OSError:
        pass


def _keep_copy(folder: Path, path: Path, data: bytes, suffix: str) -> str:
    for k in range(1, 1000):
        copy = tools.copy_before_repair(folder, path, suffix + ("" if k == 1 else f"-{k}"))
        if not copy.exists():
            break
    else:
        raise StoreError(f"{path.name} has too many copies already; nothing was changed.")
    copy.parent.mkdir(parents=True, exist_ok=True)
    with open(copy, "xb") as handle:
        handle.write(data)
    return copy.name


def _store_for(folder: Path, slot: int, data: bytes) -> Store:
    """The slot's file when it belongs to this save; an empty one when there is none.  A file of another
    village is never added to or replaced: the repair is refused and the player told."""
    store = read(folder, slot)
    if store is None:
        return Store(int(slot), roster_of(data, _offsets(data)), [])
    if not bound(store, data):
        raise StoreError(f"{FILE_NAME} for Save {slot} belongs to another village (fewer than half of the "
                         "villagers it names are in this save), so it was not changed. Nothing was changed.")
    return store


@dataclass
class MoveResult:
    moved: list[Totem]
    already: list[Totem]            # statues the file already held: their save entries were removed
    kept_alive: list[str]           # living villagers carrying the totem mark, never moved
    save: Path
    file: Path
    backup: object


def move_out(folder: Path, slot: int, processes: vv_save_backup.ProcessController | None = None,
             now: datetime | None = None) -> MoveResult:
    """Repair Saves & Logs' "Move Totems Out of the Save": every statue in the save goes into
    ElderTotems.dat and its villager entry is freed.  Refused while the game runs."""
    folder = Path(folder)
    controller = processes if processes is not None else vv_save_backup.WindowsProcesses()
    tools._refuse_if_running(folder, controller)
    save = ln.save_path(folder, GAME, slot)
    try:
        original = save.read_bytes()
        offsets = _offsets(original)
    except (OSError, totems.TotemError, ln.LastNamesError) as exc:
        raise StoreError(f"The save could not be read ({exc}); nothing was changed.") from exc
    statues = statues_in_save(original)
    alive = [_text(original, at, NAME_CAP) for at in offsets
             if original[at + totems.IS_TOTEM] != 0 and _i32(original, at + totems.HEALTH) > 0]
    if not statues:
        raise StoreError("The save holds no totem; nothing was changed."
                         + (f" ({', '.join(alive)} carry the totem mark but are alive: see "
                            f"{totems.LABEL_FIX}.)" if alive else ""))
    store = _store_for(folder, slot, original)
    moved, already = [], []
    for _k, at in statues:
        entry = _entry_at(original, at)
        if store.has(entry):
            already.append(Totem(entry))
        else:
            store.totems.append(Totem(entry))
            moved.append(Totem(entry))
    updated = _without(original, offsets, {k for k, _at in statues})
    store.roster = roster_of(updated, _offsets(updated))
    path = store_path(folder, slot)
    try:
        backup = vv_save_backup.copy_save_folder(folder, now or datetime.now(), suffix=BACKUP_MOVE)
    except vv_save_backup.BackupError as exc:
        raise StoreError(f"The backup failed, so nothing was changed. {exc}") from exc
    tools._refuse_if_running(folder, controller)
    copy = _keep_copy(folder, save, original, ".before-totems-moved-out")
    old_file = path.read_bytes() if path.exists() else None
    # The file gains the totems first; only then does the save lose them.
    try:
        _atomic_write(path, serialize(store))
        if save.read_bytes() != original:
            raise StoreError(f"{save.name} changed while it was being repaired.")
        ln._write(save, updated)
        again = save.read_bytes()
        if statues_in_save(again) or len(_offsets(again)) != len(offsets) - len(statues):
            raise StoreError("the save did not read back without its totems")
    except (OSError, StoreError, ln.LastNamesError, totems.TotemError) as exc:
        problems = []
        try:
            if save.read_bytes() != original:
                ln._write(save, original)
        except (OSError, ln.LastNamesError) as undo:
            problems.append(f"the save could not be put back ({undo})")
        try:
            if old_file is None:
                path.unlink(missing_ok=True)
            else:
                _atomic_write(path, old_file)
        except (OSError, StoreError) as undo:
            problems.append(f"{FILE_NAME} could not be put back ({undo})")
        raise StoreError(f"The repair failed ({exc}); "
                         + ("; ".join(problems) if problems else "every file was put back as it was")
                         + f". A backup is in {backup.backup_folder}.") from exc
    lines = ["Checked: every villager entry in the save marked as a totem"]
    lines += [f"Totem moved into {FILE_NAME}: {t.label()}" for t in moved]
    lines += [f"Totem already in {FILE_NAME} (its save entry freed): {t.label()}" for t in already]
    lines += [f"Not moved (alive, so a villager): {name}" for name in alive]
    lines += [f"File: {path.relative_to(folder)}", f"File: {save.relative_to(folder)} -- copy kept: {copy}",
              f"Backup: {Path(backup.backup_folder).name}"]
    _record(folder, original, slot, now, lines)
    return MoveResult(moved, already, alive, save, path, backup)


@dataclass
class PutBackResult:
    put_back: list[Totem]
    left: list[Totem]
    free: int
    save: Path
    file: Path
    backup: object

    def summary(self) -> str:
        text = f"{len(self.put_back)} totem(s) put back into the save"
        if self.left:
            text += (f"; {len(self.left)} did not fit ({self.free} free villager record(s), after every baby "
                     f"still owed) and stay in {FILE_NAME}: the stock game shows only the ones in the save")
        return text + "."


def put_back(folder: Path, slot: int, processes: vv_save_backup.ProcessController | None = None,
             now: datetime | None = None) -> PutBackResult:
    """"Put Totems Back Into the Save": each totem in ElderTotems.dat is written back into the save as the
    game keeps a totem, as many as the free villager records allow (never a villager deleted or
    overwritten, every baby still owed counted first); the rest stay in the file.  Refused while the game
    runs."""
    folder = Path(folder)
    controller = processes if processes is not None else vv_save_backup.WindowsProcesses()
    tools._refuse_if_running(folder, controller)
    save = ln.save_path(folder, GAME, slot)
    try:
        original = save.read_bytes()
        offsets = _offsets(original)
    except (OSError, totems.TotemError, ln.LastNamesError) as exc:
        raise StoreError(f"The save could not be read ({exc}); nothing was changed.") from exc
    store = read(folder, slot)
    if store is None or not store.totems:
        raise StoreError(f"Save {slot} has no {FILE_NAME} with totems in it; nothing was changed.")
    if not bound(store, original):
        raise StoreError(f"{FILE_NAME} for Save {slot} belongs to another village; nothing was changed.")
    if not offsets:
        raise StoreError("The save's villager table was not found; nothing was changed.")
    free = max(0, totems.RECORDS - len(offsets) - totems._owed(original, offsets))
    in_save = [_entry_at(original, at) for _k, at in statues_in_save(original)]
    go, left, skip = [], [], []
    for t in store.totems:
        if any(same_statue(t.entry, e) for e in in_save):
            skip.append(t)                       # already in the save: only taken off the file
        elif len(go) < free:
            go.append(t)
        else:
            left.append(t)
    if not go and not skip:
        raise StoreError(f"No villager record is free (all {totems.RECORDS} are in use or owed to babies), so "
                         "no totem could be put back; nothing was changed.")
    entries = []
    for t in go:
        entry = bytearray(t.entry)
        entry[E_IS_TOTEM] = 1
        entry[E_FLAG] = 1
        entries.append(bytes(entry))
    updated = _with(original, offsets, entries)
    path = store_path(folder, slot)
    old_file = path.read_bytes()
    remaining = Store(store.slot, roster_of(updated, _offsets(updated)), left)
    try:
        backup = vv_save_backup.copy_save_folder(folder, now or datetime.now(), suffix=BACKUP_PUT_BACK)
    except vv_save_backup.BackupError as exc:
        raise StoreError(f"The backup failed, so nothing was changed. {exc}") from exc
    tools._refuse_if_running(folder, controller)
    copy = _keep_copy(folder, save, original, ".before-totems-put-back")
    # The save gains the totems first; only then does the file lose them.
    try:
        if save.read_bytes() != original:
            raise StoreError(f"{save.name} changed while it was being repaired.")
        ln._write(save, updated)
        again = save.read_bytes()
        if len(_offsets(again)) != len(offsets) + len(go):
            raise StoreError("the totems did not read back from the save")
        _atomic_write(path, serialize(remaining))
    except (OSError, StoreError, ln.LastNamesError, totems.TotemError) as exc:
        problems = []
        try:
            if save.read_bytes() != original:
                ln._write(save, original)
        except (OSError, ln.LastNamesError) as undo:
            problems.append(f"the save could not be put back ({undo})")
        try:
            if path.read_bytes() != old_file:
                _atomic_write(path, old_file)
        except (OSError, StoreError) as undo:
            problems.append(f"{FILE_NAME} could not be put back ({undo})")
        raise StoreError(f"The repair failed ({exc}); "
                         + ("; ".join(problems) if problems else "every file was put back as it was")
                         + f". A backup is in {backup.backup_folder}.") from exc
    result = PutBackResult(go, left, free, save, path, backup)
    lines = [f"Checked: every totem in {FILE_NAME}"]
    lines += [f"Totem put back into the save: {t.label()} at ({t.x}, {t.y})" for t in go]
    lines += [f"Already in the save (taken off {FILE_NAME}): {t.label()}" for t in skip]
    lines += [f"Left in {FILE_NAME} (no villager record free): {t.label()}" for t in left]
    lines += [result.summary(), f"File: {save.relative_to(folder)} -- copy kept: {copy}",
              f"File: {path.relative_to(folder)}", f"Backup: {Path(backup.backup_folder).name}"]
    _record(folder, original, slot, now, lines)
    return result


@dataclass
class ColourResult:
    totem: Totem
    old_face: int
    new_face: int
    file: Path
    backup: object


def new_type(old: int, face: int) -> int:
    """A Totem Type with this face (type % 8), kept in the game's 1..123 (story_c2.inc c2_set_status)."""
    if not 0 <= face <= 7:
        raise StoreError("A totem colour is one of the eight faces (0 to 7).")
    value = old - ((old % 8 + 8) % 8) + face
    while value < 1:
        value += 8
    while value > 123:
        value -= 8
    return value


def list_totems(folder: Path, slot: int) -> list[Totem]:
    """The totems of the save: the ones in ElderTotems.dat when it belongs to the save, then the statues
    still in the save itself."""
    save = ln.save_path(folder, GAME, slot)
    data = save.read_bytes()
    out = []
    store = read(folder, slot)
    if store is not None and bound(store, data):
        out += store.totems
    out += [Totem(_entry_at(data, at)) for _k, at in statues_in_save(data)]
    return out


def change_colour(folder: Path, slot: int, key: str, face: int,
                  processes: vv_save_backup.ProcessController | None = None,
                  now: datetime | None = None) -> ColourResult:
    """Give the totem `key` (Totem.key) the face 0..7 of totems.png.  The totem is changed where it is:
    in ElderTotems.dat, or (the patch not in use yet) in the save.  Refused while the game runs; a key two
    totems share is refused, never guessed."""
    folder = Path(folder)
    controller = processes if processes is not None else vv_save_backup.WindowsProcesses()
    tools._refuse_if_running(folder, controller)
    save = ln.save_path(folder, GAME, slot)
    data = save.read_bytes()
    store = read(folder, slot)
    in_file = [k for k, t in enumerate(store.totems) if t.key == key] if store is not None and bound(store, data) else []
    in_save = [at for _k, at in statues_in_save(data) if Totem(_entry_at(data, at)).key == key]
    if len(in_file) + len(in_save) != 1:
        raise StoreError("That totem was not found exactly once (it may have changed); nothing was changed.")
    try:
        backup = vv_save_backup.copy_save_folder(folder, now or datetime.now(), suffix=BACKUP_COLOUR)
    except vv_save_backup.BackupError as exc:
        raise StoreError(f"The backup failed, so nothing was changed. {exc}") from exc
    tools._refuse_if_running(folder, controller)
    if in_file:
        path = store_path(folder, slot)
        old = path.read_bytes()
        t = store.totems[in_file[0]]
        entry = bytearray(t.entry)
        old_face = t.face
        struct.pack_into("<i", entry, E_TYPE, new_type(t.type, face))
        store.totems[in_file[0]] = Totem(bytes(entry))
        copy = _keep_copy(folder, path, old, ".before-totem-colour")
        try:
            _atomic_write(path, serialize(store))
        except (OSError, StoreError) as exc:
            _atomic_write(path, old)
            raise StoreError(f"The colour was not changed ({exc}); {FILE_NAME} was put back.") from exc
        changed = store.totems[in_file[0]]
    else:
        path = save
        at = in_save[0]
        t = Totem(_entry_at(data, at))
        old_face = t.face
        updated = bytearray(data)
        struct.pack_into("<i", updated, at + totems.TYPE, new_type(t.type, face))
        copy = _keep_copy(folder, save, data, ".before-totem-colour")
        ln._write(save, bytes(updated))
        changed = Totem(_entry_at(bytes(updated), at))
    _record(folder, data, slot, now, [
        f"{LABEL_COLOUR}: {changed.name}'s totem from {totems.face(old_face)} to {totems.face(face)} "
        f"(Totem Type {t.type} to {changed.type})",
        f"File: {path.relative_to(folder)} -- copy kept: {copy}", f"Backup: {Path(backup.backup_folder).name}"])
    return ColourResult(changed, old_face, face, path, backup)


# ---------------------------------------------------------------------------
# The village's setting, and the uninstall warning
# ---------------------------------------------------------------------------

def auto_give(folder: Path, slot: int) -> bool:
    """The village's "give Esteemed Elders their totems automatically" setting (off without a file)."""
    try:
        lines = settings_path(folder, slot).read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return False
    return bool(lines) and lines[0] == SETTINGS_HEADER and "auto_give\t1" in lines[1:]


def set_auto_give(folder: Path, slot: int, on: bool) -> Path:
    path = settings_path(folder, slot)
    text = f"{SETTINGS_HEADER}\nauto_give\t{1 if on else 0}\n"
    _atomic_write(path, text.encode("utf-8"))
    return path


def store_totem_count(folder: Path) -> dict[int, int]:
    """Totems kept in ElderTotems.dat, by slot (a file that cannot be read counts as -1)."""
    out = {}
    for slot in layout.SLOTS:
        try:
            store = read(folder, slot)
        except StoreError:
            out[slot] = -1
            continue
        if store is not None and store.totems:
            out[slot] = len(store.totems)
    return out


def find_totems_png(places: list[Path]) -> Path | None:
    """The game's own Images\\totems.png (eight 40 x 100 faces in one strip) in the first of these game
    folders that has it."""
    for place in places:
        candidate = Path(place) / "Images" / "totems.png"
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    return None


def save_folder_of(exe: Path) -> Path | None:
    """"<My Documents>\\LDW\\<the executable's name>": where the game keeps that copy's saves
    (native/shared/save_folder.c); None where Windows names no Documents folder."""
    try:
        import ctypes
        buffer = ctypes.create_unicode_buffer(260)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buffer) != 0:   # CSIDL_PERSONAL
            return None
        return Path(buffer.value) / "LDW" / Path(exe).stem
    except (AttributeError, OSError):
        return None


def removal_warning(installed_files: list[str], selected_ids: list[str], save_folder: Path | None) -> str | None:
    """The warning before a build that leaves this feature out replaces one that had it: totems live in
    ElderTotems.dat, which the stock game never reads."""
    if DLL not in installed_files or FEATURE_ID in selected_ids:
        return None
    counts = store_totem_count(save_folder) if save_folder is not None and Path(save_folder).is_dir() else {}
    where = ""
    if counts:
        where = " Totems kept there now: " + ", ".join(
            f"Save {slot}: {'(unreadable file)' if n < 0 else n}" for slot, n in sorted(counts.items())) + "."
    return ("This copy of The Lost Children has \"Esteemed Elders' Totems Use No Villager Records\" and the new "
            "build leaves it out. Your Esteemed Elders' totems are kept in each save's ElderTotems.dat, which the "
            "game without this patch never reads: their villages will show no totems (nothing else changes, and "
            f"the totems stay in the file).{where}\n\nTo see them without the patch, first use Repair Saves & Logs "
            f"> \"{LABEL_PUT_BACK}\" for each save (with the game closed).\n\nBuild without the patch anyway?")
