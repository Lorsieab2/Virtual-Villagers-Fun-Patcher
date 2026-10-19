"""Repair Saves & Logs, The Lost Children only: Esteemed Elders' totems.

The owner (2026-10-19):
  "Give Esteemed Elders Totems Retroactively": if an Esteemed Elder does not have a totem for whatever
  reason, they are given one of a random colour.
  "Fix Rare Villager Turning Into Totem": for unknown reasons villagers sometimes become totems; they
  have a normal Details screen but are immortal, moveable totems in the game.  The fix reverts them to
  normal villagers.

HOW THE GAME MAKES A TOTEM (stock 46C1503C...D677, read from the executable):
  0x44D4C0, every tick and in the catch-up, looks at each of the 256 records: in use (+0x30), alive
  (+0x52C > 0), not a totem (+0x558 == 0), not yet an elder (+0x7FC == 0), Master (88 or more) in at
  least three of the five skills (+0x7E4..+0x7F4), and fewer than 50 totems (0x4259B0 counts records
  with +0x558 set).  Then 0x44D190 makes the totem and 0x44D55F adds one to Village Elders
  (+0x2E514).  The totem is a NEW record, the first one not in use (scan 0x44D21B, no bound of its own;
  the patcher's safety patch stops it at record 255): +0x30 = 1; x = the elder's x, y = the elder's
  y + 10 (also kept in +0x55C / +0x560, which the loader 0x44B6C5 puts back for a totem); the name,
  sex, head, body, +0x550, lineage +0x554, both parents' names and looks, the likes and dislikes and
  the five skills copied from the elder; health 0 (0x44D467); age and +0x534 the elder's age;
  +0x524, +0x53C..+0x544, +0x5E4..+0x5EC, +0x7E0, +0x7F8, +0x7FC = 0; +0x528 the clock; +0x558 = 1
  (0x44D485, the ONLY place that sets it).  Then the ELDER's +0x7FC = 1 (0x44D4A2).  The statue shows
  totems.png frame (+0x550 mod 8) and "<name>`s totem"; nothing else of it is ever used.

THE SAVE (the game's own writer 0x44B5A0 and loader 0x44B640): every record in use, in record order,
packed into 0x2E0-byte entries: record +0x524..+0x7E3 at entry +0 (the name, record +0x564, at entry
+0x40), record +0x7E4..+0x7FF at entry +0x2C0, and a 1 at entry +0x2DC; the entry after the last has
a 0 there, and the loader (which first clears every record's +0x30 and +0x558) stops at it.  So a totem
is added by writing one more entry after the last, and a flag is cleared in place.

WHAT IS CERTAIN AND WHAT IS ASKED:
  * A record with +0x558 set and health above 0 is a living villager carrying the totem flag: the game
    never makes a totem alive (0x44D467 writes health 0 just before 0x44D485 sets the flag).  Such a
    record is reverted by clearing +0x558 alone -- every other field is the villager's own, as the save
    holds it.  (How it happens: the copy creator 0x44CEC0 -- twins, triplets, the Silver Mirror -- never
    clears +0x558, and the burial 0x465024..0x46503B frees the record it was sent to without checking it
    is still a body, so a totem made in a record freed in between is buried and its record keeps the
    flag for the next copy.  Static reading; never seen live.)
  * A totem (health 0 or less) that no Esteemed Elder of the save or the Deaths log matches, even by
    first name, is asked about: the player says whether it is a villager who turned into a totem.  A
    yes clears +0x558; the save holds health 0 for it, so it is that villager's unburied body.
  * An Esteemed Elder (a living record with +0x7FC set, or a Death record "Special villager: Esteemed
    Elder") is matched to a totem by what 0x44D190 copies: the name, sex, lineage and both parents'
    names (a dead elder: the name, sex, head and body the Death record keeps).  No totem even of the
    same first name: certainly missing.  Only a near match (same first name, something else differs,
    for instance after a rename): asked.
  * A new totem is written as 0x44D190 writes one, from the elder's own saved entry (a dead elder:
    from the Death record's name, sex, head, body and age at death; skills, likes and parents unknown,
    left empty).  +0x550 is random (1..123, the game's range), so its colour (frame +0x550 mod 8) is
    random.  The game puts it where the elder stands, which a save does not keep for the living, so it
    goes beside the campfire (about 750, 860), in a row, clear of every other totem.
  * Room: a record is needed for each totem, after every baby still owed (each living carrier's
    litter, as the patcher's own record guards count it).  With no record free, nothing is deleted or
    overwritten: the elders left without one are listed with the reason, in the confirmation and in
    the Repairs Made log.

Safety (as every Repair Saves & Logs write): refused while the game runs; the save folder is backed up
first; a copy of the save is kept in Copies Made Before Repairs; the save is written through a
temporary file and read back, and put back on any failure; one "Repair <n>" record in the Repairs Made
log names every change.
"""
from __future__ import annotations

import random
import struct
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import vv_last_names as ln
import vv_log_tools as tools
import vv_save_backup

GAME = 2
RECORDS = 256
STRIDE = 0x2E0
MAX_TOTEMS = 50                     # 0x44D4D1 / 0x44D54C: no elder is made with 50 totems standing
TYPE_RANGE = (1, 123)               # the game's +0x550 values (0x44D034..0x44D04A, the copy creator)
CAMPFIRE = (750, 860)
SPACING = 45                        # a totem frame is 40 wide (totems.png 40 x 100)
MAP_X = (60, 1640)
MAP_Y = (120, 1560)

BACKUP_GIVE = "(before giving elders totems)"
BACKUP_FIX = "(before fixing totem villagers)"
COPY_GIVE = ".before-elder-totems"
COPY_FIX = ".before-totem-villager-fix"

LABEL_GIVE = "Give Esteemed Elders Totems Retroactively"
LABEL_FIX = "Fix Rare Villager Turning Into Totem"


def _r(record_offset: int) -> int:
    """A record offset as an offset from the name (+0x564) in the saved entry."""
    return record_offset - 0x564


ENTRY = _r(0x524)                   # the entry's first byte
TIME = _r(0x528)
HEALTH = _r(0x52C)
AGE = _r(0x530)
AGE2 = _r(0x534)
SEX = _r(0x538)
CONCEIVED = _r(0x540)
LITTER = _r(0x544)
HEAD = _r(0x548)
BODY = _r(0x54C)
TYPE = _r(0x550)
LINEAGE = _r(0x554)
IS_TOTEM = _r(0x558)
X = _r(0x55C)
Y = _r(0x560)
NAME_CAP = 0x18
FATHER = _r(0x57D)
MOTHER = _r(0x596)
PARENT_CAP = 0x19
EXPECTING = (_r(0x5C0), _r(0x5E4))  # the expected father's name and looks, left by the elder's entry
INHERIT = (_r(0x5E4), _r(0x5F0))
LIKES = (_r(0x5F0), _r(0x7E0))
X7E0 = _r(0x7E0)
SKILLS = _r(0x7E4)
X7F8 = _r(0x7F8)
ELDER = _r(0x7FC)
FLAG = _r(0x524) + 0x2DC            # the entry's "in use" byte (0 after the last entry)

MALE, FEMALE = 1, 2
# The eight totem faces (totems.png frames 0..7; the Story companion's own words, story_c2.inc).
FACES = ("brown face, blue mouth", "green figure", "teal, red crest", "yellow and purple",
         "red headdress", "dark navy face", "tall carved wood", "green grinning face")


class TotemError(Exception):
    """Nothing was changed (or the save was put back); the message says why."""


def _i32(data, at: int) -> int:
    return struct.unpack_from("<i", data, at)[0]


def _text(data, at: int, cap: int) -> str:
    return bytes(data[at:at + cap]).split(b"\0", 1)[0].decode("latin-1")


def _first(name: str) -> str:
    return name.split(" ", 1)[0]


def face(totem_type: int) -> str:
    return FACES[totem_type % 8]


@dataclass
class Totem:
    at: int                         # the name's offset in the save
    record: int                     # its place among the loaded records (0 = first)
    name: str
    sex: int
    head: int
    body: int
    lineage: int
    father: str
    mother: str
    health: int
    type: int
    x: int
    y: int

    def label(self) -> str:
        return f"{self.name}'s totem (record {self.record + 1}, head {self.head}, body {self.body})"


@dataclass
class Elder:
    name: str
    sex: int
    head: int
    body: int
    living: bool
    at: int | None = None           # the living elder's name offset in the save
    record: int | None = None
    lineage: int | None = None
    father: str | None = None
    mother: str | None = None
    age: int = 0

    @property
    def key(self) -> str:
        return f"{'L' if self.living else 'D'}|{self.name}|{self.sex}|{self.head}|{self.body}|{self.record}"

    def label(self) -> str:
        what = "a living Esteemed Elder" if self.living else "an Esteemed Elder who has died"
        return f"{self.name} (head {self.head}, body {self.body}), {what}"


@dataclass
class ElderQuestion:
    elder: Elder
    totems: list[Totem]

    @property
    def key(self) -> str:
        return self.elder.key

    def question(self) -> str:
        shown = "\n".join(f"  - {t.label()}" for t in self.totems)
        return (f"{self.elder.label()} has no totem with exactly their name, sex and family, but this "
                f"totem could be theirs (a rename, for instance):\n{shown}\n\n"
                f"Is one of these {self.elder.name}'s totem?\n\nYes: they keep it and get no new one.\n"
                f"No: they are given a new totem.")


@dataclass
class TotemVillager:
    """A record carrying the totem flag that is (or may be) a villager."""
    totem: Totem
    certain: bool
    reason: str

    @property
    def key(self) -> str:
        return f"{self.totem.record}|{self.totem.name}|{self.totem.head}|{self.totem.body}"

    def describe(self) -> str:
        return f"{self.totem.name} (record {self.totem.record + 1}, head {self.totem.head}, " \
               f"body {self.totem.body}): {self.reason}"

    def question(self) -> str:
        return (f"{self.totem.label()}: {self.reason}\n\nIs this a villager who turned into a totem?\n\n"
                "Yes: the totem mark is taken off. The save holds health 0 for this record, so it becomes "
                f"{self.totem.name}'s unburied body (nothing is invented).\nNo: it stays a totem.")


@dataclass
class Survey:
    entries: int = 0
    owed: int = 0
    totems: list[Totem] = field(default_factory=list)
    elders: list[Elder] = field(default_factory=list)
    missing: list[Elder] = field(default_factory=list)          # certainly without a totem
    elder_questions: list[ElderQuestion] = field(default_factory=list)
    villagers: list[TotemVillager] = field(default_factory=list)  # certain and asked
    notes: list[str] = field(default_factory=list)

    @property
    def free(self) -> int:
        """Records a new totem may take: the unused ones less every baby still owed."""
        return max(0, RECORDS - self.entries - self.owed)

    @property
    def certain_villagers(self) -> list[TotemVillager]:
        return [v for v in self.villagers if v.certain]

    @property
    def asked_villagers(self) -> list[TotemVillager]:
        return [v for v in self.villagers if not v.certain]


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

def _offsets(data: bytes) -> list[int]:
    checker = tools.load_checker()
    try:
        return checker.villager_offsets(GAME, data, [])
    except ValueError:
        raise TotemError("The save's villager table was not found; nothing was changed.") from None


def _totem_of(data: bytes, at: int, record: int) -> Totem:
    return Totem(at, record, _text(data, at, NAME_CAP), _i32(data, at + SEX), _i32(data, at + HEAD),
                 _i32(data, at + BODY), _i32(data, at + LINEAGE), _text(data, at + FATHER, PARENT_CAP),
                 _text(data, at + MOTHER, PARENT_CAP), _i32(data, at + HEALTH), _i32(data, at + TYPE),
                 _i32(data, at + X), _i32(data, at + Y))


def _owed(data: bytes, offsets: list[int]) -> int:
    """Every baby still owed: each living record carrying (+0x540) is owed her litter (+0x544, one
    baby at least) -- scripts/build_slot_guards.py V2_OWED, the patcher's own count."""
    owed = 0
    for at in offsets:
        if _i32(data, at + HEALTH) > 0 and _i32(data, at + CONCEIVED) != 0:
            owed += max(1, _i32(data, at + LITTER))
    return owed


def _dead_elders(folder: Path, slot: int, alive: set[tuple]) -> list[Elder]:
    """The Esteemed Elders the Deaths log records ("Special villager: Esteemed Elder"), once each.  One
    still alive in the save (a log ahead of a restored save) is left to the save."""
    import vv_log_additions as additions
    out: list[Elder] = []
    seen = set()
    for b in additions.person_blocks(folder, slot, GAME):
        if not b.heading.startswith("Death") or b.value("Special villager") != "Esteemed Elder":
            continue
        name, head, body = b.identity
        if not name or head is None or body is None:
            continue
        age = b.value("Age at death")
        sex = {"Male": MALE, "Female": FEMALE}.get(b.value("Sex") or "", 0)
        key = (name, head, body, age)
        if key in seen or (name, head, body) in alive:
            continue
        seen.add(key)
        out.append(Elder(name, sex, head, body, False,
                         age=int(age) if age and age.lstrip("-").isdigit() else 0))
    return out


def _exact(e: Elder, t: Totem) -> bool:
    if e.living:
        return (t.name, t.sex, t.lineage, t.father, t.mother) == (e.name, e.sex, e.lineage, e.father, e.mother)
    return (t.name, t.head, t.body) == (e.name, e.head, e.body) and (not e.sex or t.sex == e.sex)


def _near(e: Elder, t: Totem) -> bool:
    return _first(t.name) == _first(e.name) and (not e.sex or t.sex == e.sex)


def survey_bytes(data: bytes, dead: list[Elder] | None = None, folder: Path | None = None,
                 slot: int | None = None) -> Survey:
    offsets = _offsets(data)
    s = Survey(entries=len(offsets), owed=_owed(data, offsets))
    living: list[Elder] = []
    for k, at in enumerate(offsets):
        if data[at + IS_TOTEM] != 0:
            s.totems.append(_totem_of(data, at, k))
        elif data[at + ELDER] != 0 and _i32(data, at + HEALTH) > 0:
            living.append(Elder(_text(data, at, NAME_CAP), _i32(data, at + SEX), _i32(data, at + HEAD),
                                _i32(data, at + BODY), True, at, k, _i32(data, at + LINEAGE),
                                _text(data, at + FATHER, PARENT_CAP), _text(data, at + MOTHER, PARENT_CAP),
                                _i32(data, at + AGE)))
    # The living totem flags first: they are villagers, not statues.
    statues = []
    for t in s.totems:
        if t.health > 0:
            s.villagers.append(TotemVillager(t, True, "alive (health above 0) and marked as a totem: the game "
                                                      "only ever makes a totem with health 0"))
        else:
            statues.append(t)
    if dead is None:
        alive = {(_text(data, at, NAME_CAP), _i32(data, at + HEAD), _i32(data, at + BODY)) for at in offsets
                 if data[at + IS_TOTEM] == 0 and _i32(data, at + HEALTH) > 0}
        dead = _dead_elders(folder, slot, alive) if folder is not None else []
    s.elders = living + dead
    # Each elder against the statues.
    exact = {id(e): [t for t in statues if _exact(e, t)] for e in s.elders}
    claimed: dict[int, list[Elder]] = {}
    for e in s.elders:
        for t in exact[id(e)]:
            claimed.setdefault(id(t), []).append(e)
    for e in s.elders:
        mine = exact[id(e)]
        if mine:
            # A statue two elders share exactly (the same name, sex and family): enough statues for
            # all of them, or each is asked.
            sharers = {id(x) for t in mine for x in claimed[id(t)]}
            if len(sharers) > 1 and len({id(t) for x in s.elders if id(x) in sharers for t in exact[id(x)]}) < len(sharers):
                s.elder_questions.append(ElderQuestion(e, mine))
            continue
        near = [t for t in statues if _near(e, t) and not any(x is not e for x in claimed.get(id(t), []))]
        if near:
            s.elder_questions.append(ElderQuestion(e, near))
        else:
            s.missing.append(e)
    # A statue no elder matches, even by first name: asked.
    for t in statues:
        if not any(_exact(e, t) or _near(e, t) for e in s.elders):
            s.villagers.append(TotemVillager(t, False, "no Esteemed Elder in the save or the Deaths log has "
                                                       "this name"))
    # Two statues of one elder: said, never changed.
    for e in s.elders:
        if len(exact[id(e)]) > 1:
            s.notes.append(f"{e.name} has {len(exact[id(e)])} totems (records "
                           f"{', '.join(str(t.record + 1) for t in exact[id(e)])}); they are left as they are.")
    if len(statues) >= MAX_TOTEMS:
        s.notes.append(f"The village already has {len(statues)} totems; the game itself makes no new elder "
                       f"with {MAX_TOTEMS} standing.")
    return s


def survey(folder: Path, slot: int) -> Survey:
    """The save's elders and totems, read only."""
    try:
        data = ln.save_path(folder, GAME, slot).read_bytes()
    except OSError as exc:
        raise TotemError(f"The save could not be read ({exc}).") from exc
    return survey_bytes(data, folder=Path(folder), slot=slot)


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------

def _place(taken: list[tuple[int, int]]) -> tuple[int, int]:
    """Beside the campfire, in rows, clear (30 px) of every totem already standing or placed."""
    cx, cy = CAMPFIRE
    for row in range(0, 12):
        y = cy + ((row + 1) // 2) * 110 * (1 if row % 2 else -1)       # 0, +110, -110, +220, ...
        for k in range(0, 40):
            dx = ((k + 1) // 2) * SPACING * (1 if k % 2 else -1)
            x = cx + dx
            if not (MAP_X[0] <= x <= MAP_X[1] and MAP_Y[0] <= y <= MAP_Y[1]):
                continue
            if all(abs(x - tx) >= 30 or abs(y - ty) >= 30 for tx, ty in taken):
                return x, y
    return cx, cy


def _new_entry(data: bytes, e: Elder, totem_type: int, x: int, y: int, clock: int) -> bytes:
    """A totem's saved entry, as 0x44D190 writes the record (see the module's notes)."""
    entry = bytearray(STRIDE)
    n = -ENTRY                                        # the name's offset inside the entry
    if e.at is not None:
        entry[:] = data[e.at + ENTRY:e.at + ENTRY + STRIDE]
    else:
        raw = e.name.encode("latin-1", "replace")[:NAME_CAP - 1]
        entry[n:n + NAME_CAP] = raw + bytes(NAME_CAP - len(raw))
        struct.pack_into("<i", entry, n + SEX, e.sex or 0)
        struct.pack_into("<ii", entry, n + HEAD, e.head, e.body)
        struct.pack_into("<i", entry, n + AGE, e.age)
    age = struct.unpack_from("<i", entry, n + AGE)[0]
    struct.pack_into("<iiii", entry, n + ENTRY, 0, clock, 0, age)          # +0x524, +0x528, health, age
    struct.pack_into("<i", entry, n + AGE2, age)                            # +0x534
    struct.pack_into("<iii", entry, n + _r(0x53C), 0, 0, 0)                 # +0x53C, +0x540, +0x544
    struct.pack_into("<i", entry, n + TYPE, totem_type)
    entry[n + IS_TOTEM] = 1
    struct.pack_into("<ii", entry, n + X, x, y)
    entry[n + EXPECTING[0]:n + EXPECTING[1]] = bytes(EXPECTING[1] - EXPECTING[0])
    entry[n + INHERIT[0]:n + INHERIT[1]] = bytes(INHERIT[1] - INHERIT[0])
    struct.pack_into("<i", entry, n + X7E0, 0)
    struct.pack_into("<i", entry, n + X7F8, 0)
    entry[n + ELDER] = 0
    entry[n + FLAG] = 1
    entry[n + FLAG + 1:] = bytes(STRIDE - (n + FLAG + 1))
    return bytes(entry)


def _write_save(folder: Path, slot: int, original: bytes, updated: bytes, label: str, suffix: str,
                now: datetime | None, controller, check) -> tuple[Path, object, str]:
    save = ln.save_path(folder, GAME, slot)
    try:
        backup = vv_save_backup.copy_save_folder(folder, now or datetime.now(), suffix=label)
    except vv_save_backup.BackupError as exc:
        raise TotemError(f"The backup failed, so nothing was changed. {exc}") from exc
    tools._refuse_if_running(folder, controller)
    for k in range(1, 1000):
        copy = tools.copy_before_repair(folder, save, suffix + ("" if k == 1 else f"-{k}"))
        if not copy.exists():
            break
    else:
        raise TotemError(f"{save.name} has too many copies already; nothing was changed.")
    copy.parent.mkdir(parents=True, exist_ok=True)
    with open(copy, "xb") as handle:
        handle.write(original)
    try:
        if save.read_bytes() != original:
            raise TotemError(f"{save.name} changed while it was being repaired.")
        ln._write(save, updated)
        check(save.read_bytes())
    except (OSError, TotemError, ln.LastNamesError) as exc:
        try:
            if save.read_bytes() != original:
                ln._write(save, original)
        except (OSError, ln.LastNamesError) as undo_exc:
            raise TotemError(f"The repair failed ({exc}) and the save could not be put back ({undo_exc}). "
                             f"Your backup is in {backup.backup_folder}.") from exc
        raise TotemError(f"The repair failed ({exc}); the save was put back as it was. "
                         f"A backup is in {backup.backup_folder}.") from exc
    return save, backup, copy.name


def _village(data: bytes, slot: int) -> str | None:
    import vv_corrupt_skills
    return vv_corrupt_skills._village(Path("."), GAME, slot, data)


def _record(folder: Path, village: str | None, slot: int, now: datetime | None, lines: list[str]) -> None:
    import vv_save_layout as layout
    header = village or "Village: (all villages in this save folder)"
    path, text = tools.repair_record_start(folder, GAME, header, layout.header_slot(village) or slot, now)
    text += "".join(f"  {line}\r\n" for line in lines) + "\r\n"
    with open(path, "ab") as log:
        log.write(text.encode("latin-1", "replace"))


@dataclass
class Given:
    elder: Elder
    record: int
    type: int
    x: int
    y: int

    def describe(self) -> str:
        return (f"{self.elder.label()}: a totem ({face(self.type)}, type {self.type}) at ({self.x}, {self.y}), "
                f"record {self.record + 1}")


@dataclass
class GiveResult:
    given: list[Given]
    not_given: list[tuple[Elder, str]]
    save: Path
    backup: object | None


def plan_give(s: Survey, kept: set[str] | frozenset = frozenset()) -> tuple[list[Elder], list[tuple[Elder, str]]]:
    """The elders to give a totem (certainly missing, and every asked one the player said has none --
    `kept` are the keys of those the player said already have one), and the ones that cannot be given
    one with the reason."""
    wanted = list(s.missing) + [q.elder for q in s.elder_questions if q.key not in kept]
    room = s.free
    statues = len(s.totems)                 # 0x4259B0 counts every record marked as a totem
    go, left = [], []
    for e in wanted:
        if statues + len(go) >= MAX_TOTEMS:
            left.append((e, f"the village already has {MAX_TOTEMS} totems, the most the game keeps"))
        elif len(go) >= room:
            used = s.entries
            why = (f"the village is full: {used} of {RECORDS} villager records are in use"
                   + (f" and {s.owed} more are owed to babies on the way" if s.owed else "")
                   + "; no villager is ever deleted or overwritten to make room. Repair again once a "
                     "record is free (after a death and its burial)")
            left.append((e, why))
        else:
            go.append(e)
    return go, left


def give_totems(folder: Path, slot: int, kept: set[str] | frozenset = frozenset(),
                processes: vv_save_backup.ProcessController | None = None, now: datetime | None = None,
                rng: random.Random | None = None) -> GiveResult:
    """Give every Esteemed Elder without a totem a new one of a random colour, as many as the free records
    allow; the rest are listed (never a villager deleted or overwritten).  Refused while the game runs."""
    folder = Path(folder)
    controller = processes if processes is not None else vv_save_backup.WindowsProcesses()
    tools._refuse_if_running(folder, controller)
    rng = rng or random.Random()
    save = ln.save_path(folder, GAME, slot)
    try:
        original = save.read_bytes()
        s = survey_bytes(original, folder=folder, slot=slot)
    except (struct.error, OSError, ln.LastNamesError) as exc:
        raise TotemError(f"The save could not be read ({exc}); nothing was changed.") from exc
    go, left = plan_give(s, kept)
    if not go and not left:
        raise TotemError("Every Esteemed Elder already has a totem; nothing was changed.")
    offsets = _offsets(original)
    first = offsets[0] if offsets else None
    village = _village(original, slot)
    lines = ["Checked: every Esteemed Elder in the save and the Deaths log, for a totem of their own"]
    given: list[Given] = []
    backup = None
    if go:
        if first is None:
            raise TotemError("The save's villager table was not found; nothing was changed.")
        updated = bytearray(original)
        clock = max((_i32(original, at + TIME) for at in offsets), default=0)
        taken = [(t.x, t.y) for t in s.totems]
        n = len(offsets)
        for e in go:
            x, y = _place(taken)
            taken.append((x, y))
            kind = rng.randint(*TYPE_RANGE)
            at = first + n * STRIDE
            if at + ENTRY + STRIDE > len(updated):
                raise TotemError("The save is shorter than its villager table; nothing was changed.")
            updated[at + ENTRY:at + ENTRY + STRIDE] = _new_entry(original, e, kind, x, y, clock)
            given.append(Given(e, n, kind, x, y))
            n += 1
        # The loader stops at the first entry not in use: the one after the last, while one exists in the
        # table (the writer 0x44B629 writes the same 0 even after record 256).
        end = first + n * STRIDE + FLAG
        if end < len(updated):
            updated[end] = 0
        want = s.entries + len(given)

        def check(after: bytes) -> None:
            again = _offsets(after)
            if len(again) != want or any(after[a + IS_TOTEM] == 0 for a in again[s.entries:]):
                raise TotemError("the totems did not read back from the save")

        save, backup, copy = _write_save(folder, slot, original, bytes(updated), BACKUP_GIVE, COPY_GIVE, now,
                                         controller, check)
        lines += [f"Totem given: {g.describe()}" for g in given]
        lines += [f"File: {Path(save).relative_to(folder)} -- copy kept: {copy}",
                  f"Backup: {Path(backup.backup_folder).name}"]
    lines += [f"Not given: {e.label()} -- {why}" for e, why in left]
    if not go:
        lines.append("Nothing was changed in the save.")
    try:
        _record(folder, village, slot, now, lines)
    except OSError:
        pass                                    # the totems stand; the save shows them
    return GiveResult(given, left, save, backup)


@dataclass
class FixResult:
    fixed: list[TotemVillager]
    save: Path
    backup: object


def fix_totem_villagers(folder: Path, slot: int, confirmed: set[str] | frozenset = frozenset(),
                        processes: vv_save_backup.ProcessController | None = None,
                        now: datetime | None = None) -> FixResult:
    """Take the totem mark off every living villager carrying it, and off every asked record the player
    said is a villager (`confirmed`: their keys).  Only the +0x558 byte changes.  Refused while the game
    runs."""
    folder = Path(folder)
    controller = processes if processes is not None else vv_save_backup.WindowsProcesses()
    tools._refuse_if_running(folder, controller)
    save = ln.save_path(folder, GAME, slot)
    try:
        original = save.read_bytes()
        s = survey_bytes(original, folder=folder, slot=slot)
    except (struct.error, OSError, ln.LastNamesError) as exc:
        raise TotemError(f"The save could not be read ({exc}); nothing was changed.") from exc
    chosen = [v for v in s.villagers if v.certain or v.key in confirmed]
    if not chosen:
        raise TotemError("No villager carries the totem mark; nothing was changed.")
    updated = bytearray(original)
    for v in chosen:
        updated[v.totem.at + IS_TOTEM] = 0
    places = {v.totem.at + IS_TOTEM for v in chosen}

    def check(after: bytes) -> None:
        if any(after[p] != 0 for p in places) or len(after) != len(original) or any(
                after[i] != original[i] for i in range(len(original)) if i not in places):
            raise TotemError("the save did not read back as repaired")

    save, backup, copy = _write_save(folder, slot, original, bytes(updated), BACKUP_FIX, COPY_FIX, now,
                                     controller, check)
    lines = ["Checked: every record in the save marked as a totem, for a villager who turned into one"]
    for v in chosen:
        how = "certain" if v.certain else "the player said it is a villager"
        lines.append(f"Reverted to a villager ({how}): {v.describe()} -- the totem mark (record +0x558) "
                     "cleared; every other field kept as the save holds it")
    lines += [f"File: {Path(save).relative_to(folder)} -- copy kept: {copy}",
              f"Backup: {Path(backup.backup_folder).name}"]
    try:
        _record(folder, _village(original, slot), slot, now, lines)
    except OSError:
        pass
    return FixResult(chosen, save, backup)
