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
    names (a dead elder: the name, sex, head and body the Death record keeps), or by a rename the
    records hold (a "Name changed" record or an answered rename, with the same looks and sex).  A
    renamed villager is the same person, so a near match is asked: the same first name, or the same
    head, body, sex and (a living elder) family line under another name.  No totem matching even so:
    certainly missing.  A totem that is or may be an elder's is never asked about as a villager.
  * The answers are one to one (`ask`, `allocate`): a statue accepted for one elder is not asked about
    for any other, and the other elders it could have been are given a new totem.  A statue is never
    removed or duplicated on a guess.
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
import re
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
# The eight totem colours, numbered 1 to 8 as the Change Totem Colour window shows the game's own totems
# from left to right (totems.png frames 0..7) -- never described by how they look (the owner, v1.35.80).
# The same numbers everywhere: the Story companion (story_c2.inc) and the Island Events log
# (island_event_more.inc) use them too.
FACES = tuple(f"colour {n}" for n in range(1, 9))


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
    in_store: bool = False          # kept in ElderTotems.dat (src/vv_vv2_totem_store.py), not in the save

    def label(self) -> str:
        where = "in ElderTotems.dat" if self.in_store else f"record {self.record + 1}"
        return f"{self.name}'s totem ({where}, head {self.head}, body {self.body})"


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
        return (f"{'L' if self.living else 'D'}|{self.name}|{self.sex}|{self.head}|{self.body}|{self.record}"
                f"|{self.age}")

    def label(self) -> str:
        what = "a living Esteemed Elder" if self.living else "an Esteemed Elder who has died"
        return f"{self.name} (head {self.head}, body {self.body}), {what}"


@dataclass
class ElderQuestion:
    """One elder and one statue that may be theirs.  Answers are one to one (`allocate`): a statue is
    accepted for one elder at most, and an elder keeps one statue at most."""
    elder: Elder
    totem: Totem
    why: str
    others: list[Elder] = field(default_factory=list)   # the other elders this statue could belong to

    @property
    def key(self) -> str:
        return f"{self.elder.key}#{self.totem.record}"

    def question(self) -> str:
        also = ""
        if self.others:
            also = (f"\n\nThis statue could also be {', '.join(o.name for o in self.others)}'s. A totem is one "
                    f"elder's only: if it is {self.elder.name}'s, it is not asked about for anyone else.")
        return (f"{self.elder.label()} has no totem that is certainly theirs, but this totem could be "
                f"theirs ({self.why}):\n  - {self.totem.label()}{also}\n\n"
                f"Is this {self.elder.name}'s totem?\n\nYes: it is theirs alone; they keep it and get no new one.\n"
                f"No: it is not theirs. Any other totem that could be theirs is asked about next; with none, "
                f"they are given a new totem.")


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
    in_store: bool = False          # the save's ElderTotems.dat is in use: new totems go there, need no record
    totems: list[Totem] = field(default_factory=list)
    elders: list[Elder] = field(default_factory=list)
    missing: list[Elder] = field(default_factory=list)          # certainly without a totem
    elder_questions: list[ElderQuestion] = field(default_factory=list)
    villagers: list[TotemVillager] = field(default_factory=list)  # certain and asked
    notes: list[str] = field(default_factory=list)

    @property
    def free(self) -> int:
        """Records a new totem may take: the unused ones less every baby still owed.  With the save's
        ElderTotems.dat in use a totem takes no record, so there is always room."""
        if self.in_store:
            return 1 << 30
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


def _renames(folder: Path, slot: int) -> set[tuple[str, str, int, int]]:
    """Every rename the records hold for this slot's village, as (old name, new name, head, body): the
    "Name changed" records of the Births and Conceptions log, and the renames the player answered in
    Check / Repair Saves & Logs ("Keep as is: NEW is right (I renamed them)") -- the same two sources the
    Family Tree joins a renamed villager by (vv_genealogy._logged_renames, _answered_renames).  Read only;
    a log that cannot be read adds nothing (the elder is then asked, never guessed)."""
    import vv_log_additions as additions
    out: set[tuple[str, str, int, int]] = set()
    try:
        checker = tools.load_checker()
        villages = additions.current_villages(folder, GAME, slot)
        for path in checker.log_files(folder):
            if "Births and Conceptions" not in path.name:
                continue
            for b in additions.blocks(path):
                if b.heading != "Name changed" or not b.of(slot, GAME, villages):
                    continue
                new, head, body = b.identity
                old = b.value("Old name")
                if new and old and old != new and head is not None and body is not None:
                    out.add((old, new, head, body))
    except (OSError, ValueError):
        pass
    try:
        import vv_reconcile as reconcile
        answers = reconcile.answered(folder, GAME, slot, additions.current_villages(folder, GAME, slot))
    except (OSError, ValueError):
        answers = {}
    for key, answer in answers.items():
        parts = key.split("|")
        if len(parts) != 5 or parts[0] != "rename":
            continue
        _topic, old, head, body, new = parts
        if answer != f"{reconcile.KEEP}: {new} is right (I renamed them)" or not old or not new or old == new:
            continue
        if head.lstrip("-").isdigit() and body.lstrip("-").isdigit():
            out.add((old, new, int(head), int(body)))
    out |= _patcher_renames(folder, slot)
    return out


_RENAMED_LINE = re.compile(r"^\s*Renamed: (.+) \(head (-?\d+), body (-?\d+)(?:, age -?\d+)?\) -> (.+?)\s*$")


def _patcher_renames(folder: Path, slot: int) -> set[tuple[str, str, int, int]]:
    """The renames the patcher itself made in this village (the owner, v1.35.80: a totem follows its elder
    through them, never asked): the ones kept in the Log Decisions file (vv_log_decisions.ALIAS_KIND --
    Last Names, Number Duplicate Names, cut names restored, a name given back) and the "Renamed: <old>
    (head h, body b) -> <new>" lines of the Repairs Made log (Number Duplicate Names before v1.35.80).
    Read only; what cannot be read adds nothing."""
    import vv_log_additions as additions
    import vv_log_decisions as decisions
    import vv_save_layout as layout
    out: set[tuple[str, str, int, int]] = set()
    try:
        villages = additions.current_villages(folder, GAME, slot)
    except (OSError, ValueError):
        villages = None
    try:
        for d in decisions.load(Path(folder), GAME, slot):
            if d.get("kind") != decisions.ALIAS_KIND or not isinstance(d.get("name"), str) \
                    or not isinstance(d.get("field"), str):
                continue
            if villages is not None and d.get("village") is not None and d.get("village") not in villages:
                continue
            head, body = d.get("head"), d.get("body")
            if isinstance(head, int) and isinstance(body, int) and d["name"] and d["field"] != d["name"]:
                out.add((d["name"], d["field"], head, body))
    except (OSError, ValueError):
        pass
    try:
        checker = tools.load_checker()
        for path in checker.game_logs(Path(folder), layout.REPAIRS_LOGS, f"Virtual Villagers {GAME} Repairs Log"):
            try:
                found = additions.blocks(path)
            except OSError:
                continue
            for b in found:
                if not b.of(slot, GAME, villages):
                    continue
                for line in b.lines:
                    m = _RENAMED_LINE.match(line)
                    if m and m.group(1) != m.group(4):
                        out.add((m.group(1), m.group(4), int(m.group(2)), int(m.group(3))))
    except (OSError, ValueError, AttributeError):
        pass
    return out


def _unnumbered(name: str) -> str:
    """A name without the Roman number Number Duplicate Names gives ("Azizi Kalama I" -> "Azizi Kalama")."""
    words = name.split(" ")
    if len(words) > 1 and re.fullmatch(r"[IVXLCDM]+", words[-1]):
        return " ".join(words[:-1])
    return name


def _renamed(e: Elder, t: Totem, renames: set[tuple[str, str, int, int]]) -> bool:
    """The records say the statue's name became the elder's (a chain of renames, with the looks the
    statue copied and the elder still has, and the same sex)."""
    if (t.head, t.body) != (e.head, e.body) or (e.sex and t.sex != e.sex) or t.name == e.name:
        return False
    # The patcher's numbering: the statue keeps the name the elder had before Number Duplicate Names gave
    # them a number (or a number the elder has since), the same looks and sex -- and, for a living elder,
    # the family line the statue copied.  Two numbered namesakes it could both be are asked (one to one).
    if _unnumbered(t.name) == _unnumbered(e.name) and (not e.living or t.lineage == e.lineage):
        return True
    seen, todo = {t.name}, [t.name]
    while todo:
        name = todo.pop()
        for old, new, head, body in renames:
            if old == name and (head, body) == (t.head, t.body) and new not in seen:
                if new == e.name:
                    return True
                seen.add(new)
                todo.append(new)
    return False


def _maybe(e: Elder, t: Totem) -> str | None:
    """Why the statue could be the elder's although nothing certain says so; None when nothing does.
    The first name (a last name given or changed), or what 0x44D190 copies that a rename leaves alone:
    the head, the body, the sex and (a living elder) the family line."""
    if e.sex and t.sex != e.sex:
        return None
    if _first(t.name) == _first(e.name):
        return "the same first name"
    if (t.head, t.body) == (e.head, e.body) and t.sex in (MALE, FEMALE) and (not e.living or t.lineage == e.lineage):
        return ("the same head, body, sex and family line, under another name" if e.living
                else "the same head, body and sex, under another name")
    return None


def allocate(s: "Survey", kept: set[str] | frozenset) -> set[str]:
    """The elders (their keys) who keep a statue, from the answered questions' keys `kept`: one to one,
    in the survey's order -- a statue accepted for one elder is no one else's, and an elder keeps one."""
    elders: set[str] = set()
    taken: set[int] = set()
    for q in s.elder_questions:
        if q.key in kept and q.elder.key not in elders and q.totem.record not in taken:
            elders.add(q.elder.key)
            taken.add(q.totem.record)
    return elders


def ask(s: "Survey", answer) -> set[str]:
    """Ask the player each question in turn (`answer(question) -> bool`), one to one: once a statue is
    accepted for an elder, it is not asked about for any other elder, and that elder is asked no more.
    Returns the accepted questions' keys (for plan_give / give_totems)."""
    kept: set[str] = set()
    elders: set[str] = set()
    taken: set[int] = set()
    for q in s.elder_questions:
        if q.elder.key in elders or q.totem.record in taken:
            continue
        if answer(q):
            kept.add(q.key)
            elders.add(q.elder.key)
            taken.add(q.totem.record)
    return kept


def _stored(folder: Path, slot: int, data: bytes) -> list[Totem] | None:
    """The totems in the save's ElderTotems.dat (src/vv_vv2_totem_store.py), when it is there and belongs to
    this save; None when the file is not in use.  A file of another village or one that cannot be read is
    refused, never guessed at."""
    import vv_vv2_totem_store as store_mod
    try:
        store = store_mod.read(folder, slot)
    except store_mod.StoreError as exc:
        raise TotemError(f"The save's {store_mod.FILE_NAME} could not be read ({exc}); nothing was changed.") from exc
    if store is None:
        return None
    if not store_mod.bound(store, data):
        raise TotemError(f"The save's {store_mod.FILE_NAME} belongs to another village; nothing was changed.")
    return [Totem(-1, 100000 + k, t.name, t.sex, t.head, t.body, t.lineage, t.father, t.mother,
                  _i32(t.entry, 0x08), t.type, t.x, t.y, True) for k, t in enumerate(store.totems)]


def survey_bytes(data: bytes, dead: list[Elder] | None = None, folder: Path | None = None,
                 slot: int | None = None, renames: set[tuple[str, str, int, int]] | None = None,
                 stored: list[Totem] | None = None) -> Survey:
    offsets = _offsets(data)
    s = Survey(entries=len(offsets), owed=_owed(data, offsets), in_store=stored is not None)
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
    # The totems kept in ElderTotems.dat are statues too (an elder who has one there has a totem).
    s.totems += stored or []
    statues += stored or []
    if dead is None:
        alive = {(_text(data, at, NAME_CAP), _i32(data, at + HEAD), _i32(data, at + BODY)) for at in offsets
                 if data[at + IS_TOTEM] == 0 and _i32(data, at + HEALTH) > 0}
        dead = _dead_elders(folder, slot, alive) if folder is not None else []
    s.elders = living + dead
    if renames is None:
        renames = _renames(folder, slot) if folder is not None else set()
    # Each elder against the statues: certain by the copied fields, or by a recorded rename.
    exact = {id(e): [t for t in statues if _exact(e, t) or _renamed(e, t, renames)] for e in s.elders}
    claimed: dict[int, list[Elder]] = {}
    for e in s.elders:
        for t in exact[id(e)]:
            claimed.setdefault(id(t), []).append(e)
    for e in s.elders:
        mine = exact[id(e)]
        if mine:
            # A statue two elders share exactly (the same name, sex and family): enough statues for
            # all of them, or each pair is asked (one to one: `ask` / `allocate`).
            sharers = {id(x) for t in mine for x in claimed[id(t)]}
            if len(sharers) > 1 and len({id(t) for x in s.elders if id(x) in sharers for t in exact[id(x)]}) < len(sharers):
                s.elder_questions += [ElderQuestion(e, t, "the same name, sex and family as another elder's")
                                      for t in mine]
            continue
        found = False
        for t in statues:
            # A statue certainly another elder's is never offered.
            why = None if any(x is not e for x in claimed.get(id(t), [])) else _maybe(e, t)
            if why:
                s.elder_questions.append(ElderQuestion(e, t, why))
                found = True
        if not found:
            s.missing.append(e)
    # Each question names the other elders the same statue could belong to.
    for q in s.elder_questions:
        q.others = [x.elder for x in s.elder_questions if x.totem is q.totem and x.elder is not q.elder]
    # A statue that is (or may be) an elder's is never offered as a villager; one no elder matches, by
    # name, rename or looks, is asked.
    spoken = {id(t) for ts in exact.values() for t in ts} | {id(q.totem) for q in s.elder_questions}
    for t in statues:
        if id(t) not in spoken and not t.in_store:
            s.villagers.append(TotemVillager(t, False, "no Esteemed Elder in the save or the Deaths log has "
                                                       "this name or these looks"))
        elif id(t) not in spoken:
            s.notes.append(f"{t.label()}: no Esteemed Elder in the save or the Deaths log has this name or "
                           "these looks; it is left as it is.")
    # Two statues of one elder: said, never changed.
    for e in s.elders:
        if len(exact[id(e)]) > 1:
            s.notes.append(f"{e.name} has {len(exact[id(e)])} totems (records "
                           f"{', '.join(str(t.record + 1) for t in exact[id(e)])}); they are left as they are.")
    if len(statues) >= MAX_TOTEMS and not s.in_store:
        s.notes.append(f"The village already has {len(statues)} totems; the game itself makes no new elder "
                       f"with {MAX_TOTEMS} standing.")
    return s


def survey(folder: Path, slot: int) -> Survey:
    """The save's elders and totems, read only."""
    try:
        data = ln.save_path(folder, GAME, slot).read_bytes()
    except OSError as exc:
        raise TotemError(f"The save could not be read ({exc}).") from exc
    return survey_bytes(data, folder=Path(folder), slot=slot, stored=_stored(Path(folder), slot, data))


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
        where = "in ElderTotems.dat" if self.record < 0 else f"record {self.record + 1}"
        return f"{self.elder.label()}: a totem ({face(self.type)}, type {self.type}) at ({self.x}, {self.y}), {where}"


@dataclass
class GiveResult:
    given: list[Given]
    not_given: list[tuple[Elder, str]]
    save: Path
    backup: object | None


def plan_give(s: Survey, kept: set[str] | frozenset = frozenset()) -> tuple[list[Elder], list[tuple[Elder, str]]]:
    """The elders to give a totem (certainly missing, and every asked one not given a statue -- `kept`
    are the keys of the questions the player answered yes, taken one to one by `allocate`, so one statue
    never stands for two elders), and the ones that cannot be given one with the reason."""
    keeping = allocate(s, kept)
    wanted = list(s.missing)
    for q in s.elder_questions:
        if q.elder.key not in keeping and all(q.elder is not e for e in wanted):
            wanted.append(q.elder)
    room = s.free
    statues = len(s.totems)                 # 0x4259B0 counts every record marked as a totem
    go, left = [], []
    for e in wanted:
        if not s.in_store and statues + len(go) >= MAX_TOTEMS:
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
        s = survey_bytes(original, folder=folder, slot=slot, stored=_stored(folder, slot, original))
    except (struct.error, OSError, ln.LastNamesError) as exc:
        raise TotemError(f"The save could not be read ({exc}); nothing was changed.") from exc
    go, left = plan_give(s, kept)
    if not go and not left:
        raise TotemError("Every Esteemed Elder already has a totem; nothing was changed.")
    if s.in_store and go:
        return _give_into_store(folder, slot, original, s, go, left, controller, now, rng)
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


def _give_into_store(folder: Path, slot: int, original: bytes, s: Survey, go: list[Elder],
                     left: list[tuple[Elder, str]], controller, now: datetime | None,
                     rng: random.Random) -> GiveResult:
    """The new totems go into the save's ElderTotems.dat (they take no villager record); the save itself is
    not changed.  Backed up first; the file is written through a temporary file and read back."""
    import vv_vv2_totem_store as store_mod
    store = store_mod.read(folder, slot)
    offsets = _offsets(original)
    clock = max((_i32(original, at + TIME) for at in offsets), default=0)
    taken = [(t.x, t.y) for t in s.totems]
    given: list[Given] = []
    for e in go:
        x, y = _place(taken)
        taken.append((x, y))
        kind = rng.randint(*TYPE_RANGE)
        store.totems.append(store_mod.Totem(_new_entry(original, e, kind, x, y, clock)))
        store.village = store.village or store_mod.village_of(original)
        given.append(Given(e, -1, kind, x, y))
    path = store_mod.store_path(folder, slot)
    old = path.read_bytes()
    try:
        backup = vv_save_backup.copy_save_folder(folder, now or datetime.now(), suffix=BACKUP_GIVE)
    except vv_save_backup.BackupError as exc:
        raise TotemError(f"The backup failed, so nothing was changed. {exc}") from exc
    tools._refuse_if_running(folder, controller)
    copy = store_mod._keep_copy(folder, path, old, COPY_GIVE)
    try:
        store_mod._atomic_write(path, store_mod.serialize(store))
        if len(store_mod.parse(path.read_bytes()).totems) != len(store.totems):
            raise TotemError("the totems did not read back from ElderTotems.dat")
    except (OSError, store_mod.StoreError, TotemError) as exc:
        try:
            store_mod._atomic_write(path, old)
        except (OSError, store_mod.StoreError):
            pass
        raise TotemError(f"The repair failed ({exc}); ElderTotems.dat was put back. "
                         f"A backup is in {backup.backup_folder}.") from exc
    lines = ["Checked: every Esteemed Elder in the save and the Deaths log, for a totem of their own"]
    lines += [f"Totem given (in ElderTotems.dat): {g.elder.label()}: a totem ({face(g.type)}, type {g.type}) at "
              f"({g.x}, {g.y})" for g in given]
    lines += [f"Not given: {e.label()} -- {why}" for e, why in left]
    lines += [f"File: {path.relative_to(folder)} -- copy kept: {copy}", f"Backup: {Path(backup.backup_folder).name}"]
    try:
        _record(folder, _village(original, slot), slot, now, lines)
    except OSError:
        pass
    return GiveResult(given, left, path, backup)


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
