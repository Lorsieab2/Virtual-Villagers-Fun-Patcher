"""Repair Saves & Logs' "Fix grave information" (all five games).

The owner (2026-10-10): "add an option in Repair logs/saves to fix grave information too: Name, age,
etc." and "account for mod-added stuff too".  Each grave in the save is compared with its Death record
in the Deaths log, with the patcher's own grave files and with the villager's other records; every
difference is listed in plain words and the player chooses, grave by grave and field by field, which
value is right -- or "Don't know / leave it", which changes nothing (nothing is pre-decided).  Then
"Retroactively edit records?" as for every contradiction (src/vv_log_decisions.py): Yes corrects the
Death record (and the Epitaph changed records of that grave) too; No leaves every record as it is and
remembers the answer, so the same difference is not asked again.  The player may also edit a grave
directly (a name, an age... that is simply wrong).

WHAT A GRAVE HOLDS (from each game's own burial writer and grave loader):

  A New Home       manager +0xA31C (save 0xA320), 50 x 0x2C: name char[0x1C], best skill +0x1C,
                   job +0x20 (1 Farmer, 2 Parent, 3 Scientist, 4 Builder, 5 Doctor), age +0x24.
                   The patcher's Graves file keeps the cause and the epitaph (VCD1, by the grave's
                   name-and-age fingerprint): the game itself has neither.
  The Lost Children world +0x2EB0C (save 0x2EB10), 50 x 0x7C: name char[0x19], epitaph char[0x41]
                   +0x19, best skill +0x6C, job +0x70 (1 Farmer, 2 Parent, 3 Doctor, 4 Scientist,
                   5 Builder), age +0x74.  The cause is in the patcher's Graves file.
  The Secret City  the Roster of the Dead (writer 0x454FF0; save 0xF0C), 500 x 0x30: name char[0x19],
                   age +0x1C, job +0x20 (0 Farmer .. 4 Builder), best skill +0x24, Tribal Chief
                   byte +0x28 (the record's +0xE80), Esteemed Elder byte +0x29, cause +0x2C.  The first
                   50 also get a gravestone (save 0x598, 50 x 0x2C): its roster place +0, best skill
                   +4, epitaph char[0x20] +8; -1 = no stone.
  The Tree of Life the Roster of the Dead (writer 0x45D470; save 0x908), 500 x 0x5C: name char[0x19],
                   age +0x1C, head +0x20, body +0x24, job +0x28, best skill +0x2C, Esteemed Elder
                   byte +0x31, child byte +0x32 (age under 280), male byte +0x33, cause +0x34,
                   epitaph char[0x20] +0x38.  The loader (0x45D6E0) ends the list at the first age 0,
                   refuses the WHOLE save for a name with no NUL in 0x19 bytes, a negative age, a job
                   or a cause outside -1..4.
  New Believers    the same (writer 0x464C70, save 0x86C, loader 0x464EE0: a job -1..5, the Devotee).

  Every game's burial treats a grave of age 0 as an empty place (its next burial reuses it), so a
  grave is never given age 0 here: 0 is a real age (the owner, 2026-10-09), but not one a grave can
  keep.  Only full villagers have graves (the owner, 2026-10-09: a nursing baby never gets one), and
  New Believers never makes a Heathen's grave (the owner, 2026-09-30): nothing here makes a grave.

  THE PATCHER'S OWN DATA ABOUT A GRAVE.  The Death record (Name, Custom title, Special villager, Mask,
  Age at death, Sex, Cause of death, Grave, Epitaph, Head, Body, ...), later "Epitaph changed" records
  (the newest names the epitaph the grave should have), the Graves file (A New Home, The Lost
  Children: cause, epitaph), Graves Logged (every game: which graves have their record, by
  fingerprint), the last-names record (Last Names - Save N.dat: each villager's last name), and the
  villager's living snapshots (their Custom title and Mask before they died).

Safety (as every Repair Saves & Logs write): refused while the game runs; the save folder is backed
up first; each file is copied into Data\\Copies Made Before Repairs; every file is written through a
temporary file, swapped in and read back, and any failure puts every changed file back; a "Repair
<n>" entry goes into the Repairs Made log.
"""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import vv_last_names as ln
import vv_log_tools as tools
import vv_save_backup

BACKUP_LABEL = "(before fixing graves)"
COPY_SUFFIX = ".before-grave-repair"
DONT_KNOW = "Don't know / leave it"
DECISION_KIND = "grave"

# New Believers' words (the owner, 2026-10-03: causes and epitaphs use VV5's spelling); the
# patcher's Cause of Death companion writes these (native/vvfp_cause_of_death).
CAUSE_WORDS = {-1: "Unknown causes", 0: "Disease", 1: "Starvation", 2: "Old age", 3: "Work accident",
               4: "Act of Nature"}
CAUSE_NONE = 0x7F
NOT_RECORDED = "(not recorded"
EPITAPHS = (None, "Respected Citizen", "Child of the Earth", "Nature's Friend", "Parent, Teacher, Friend",
            "Dedicated to Children", "Guardian of Health", "Dedicated to Others", "Dedicated Student",
            "Inspired Inventor", "Inspired Architect", "Strong Arms, Big Heart", "Curious and Playful",
            "Loving and Special")
CHILD_AGE = 280                     # under 14 years: "Apprentice" (A New Home, The Lost Children, VV4)


@dataclass(frozen=True)
class Layout:
    base: int
    places: int
    stride: int
    name_cap: int                   # the name field
    age: int
    job: int
    value: int
    jobs: tuple                     # job words by value
    first_job: int                  # the lowest job value that names a job
    master: int
    epitaph: tuple | None = None    # (offset, field bytes) in the grave
    cause: int | None = None
    head: int | None = None
    body: int | None = None
    male: int | None = None
    elder: int | None = None
    chief: int | None = None
    child: int | None = None
    apprentice: bool = False        # the patcher's / game's "Apprentice" for a child's grave


LAYOUTS = {
    1: Layout(0xA320, 50, 0x2C, 0x1C, 0x24, 0x20, 0x1C,
              (None, "Farmer", "Parent", "Scientist", "Builder", "Doctor"), 1, 90, apprentice=True),
    2: Layout(0x2EB10, 50, 0x7C, 0x19, 0x74, 0x70, 0x6C,
              (None, "Farmer", "Parent", "Doctor", "Scientist", "Builder"), 1, 88, epitaph=(0x19, 0x41),
              apprentice=True),
    3: Layout(0xF0C, 500, 0x30, 0x19, 0x1C, 0x20, 0x24,
              ("Farmer", "Parent", "Doctor", "Scientist", "Builder"), 0, 88, cause=0x2C, chief=0x28, elder=0x29),
    4: Layout(0x908, 500, 0x5C, 0x19, 0x1C, 0x28, 0x2C,
              ("Farmer", "Parent", "Doctor", "Scientist", "Builder"), 0, 88, epitaph=(0x38, 0x20), cause=0x34,
              head=0x20, body=0x24, male=0x33, elder=0x31, child=0x32, apprentice=True),
    5: Layout(0x86C, 500, 0x5C, 0x19, 0x1C, 0x28, 0x2C,
              ("Farmer", "Parent", "Doctor", "Scientist", "Builder", "Devotee"), 0, 88, epitaph=(0x38, 0x20),
              cause=0x34, head=0x20, body=0x24, male=0x33, elder=0x31, child=0x32),
}
VV3_STONES = (0x598, 50, 0x2C, 8, 0x20)            # file offset, count, stride, epitaph, field bytes
EPITAPH_ROOM = {1: 31, 2: 64, 3: 31, 4: 31, 5: 31}

# The fields, in the order the window shows them, with their plain-words names.
FIELDS = {
    "name": "Name", "age": "Age at death", "sex": "Sex", "head": "Head", "body": "Body",
    "cause": "Cause of death", "grave": "Grave (job)", "epitaph": "Epitaph",
    "title": "Special villager", "custom": "Custom title", "mask": "Mask",
}
# The Death record's line for each field.
RECORD_LINE = {"name": "Name", "age": "Age at death", "sex": "Sex", "head": "Head", "body": "Body",
               "cause": "Cause of death", "grave": "Grave", "epitaph": "Epitaph", "title": "Special villager",
               "custom": "Custom title", "mask": "Mask"}
# Lines a Death record may lack, put where the patcher writes them: after these.
INSERT_AFTER = {"custom": ("Name",), "title": ("Custom title", "Name"), "mask": ("Special villager", "Custom title", "Name")}
TITLE_RANK = ("Tribal Chief", "Retired Heathen Chief", "Heathen Mommy", "Former Heathen", "Former Heathen Master",
              "Golden Child", "Esteemed Elder", "Scholar")


class GraveError(Exception):
    """Nothing was changed (or everything was put back); the message says why."""


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

@dataclass
class Grave:
    place: int                      # the grave's place in the game's table (its order of burial)
    at: int                         # its offset in the save
    values: dict                    # field -> value (str / int), what the grave itself keeps
    fingerprint: int
    stone: int | None = None        # The Secret City: the gravestone's offset, when it has one
    sidecar: dict = field(default_factory=dict)  # field -> value from the patcher's Graves file
    record: object = None           # its Death record (vv_log_additions.Block), when one is found

    @property
    def name(self) -> str:
        return self.values["name"]

    @property
    def age(self) -> int:
        return self.values["age"]

    def label(self) -> str:
        return f"{self.name} (grave {self.place + 1}, age at death {self.age})"


def _i32(data, at: int) -> int:
    return struct.unpack_from("<i", data, at)[0]


def _text(data, at: int, cap: int) -> str:
    return bytes(data[at:at + cap]).split(b"\0", 1)[0].decode("latin-1")


def grave_line(game: int, job: int, value: int, age: int) -> str:
    """The skill line the grave shows under "Job" (cod_grave_title / v345_title)."""
    lay = LAYOUTS[game]
    if not 0 <= job < len(lay.jobs) or lay.jobs[job] is None or value < 20:
        return "Untrained"
    if lay.apprentice and age < CHILD_AGE:
        rank = "Apprentice"
    else:
        rank = "Trainee" if value < 50 else "Adept" if value < lay.master else "Master"
    return f"{rank} {lay.jobs[job]}"


def _title_of(lay: Layout, data, at: int) -> str:
    if lay.chief is not None and data[at + lay.chief]:
        return "Tribal Chief"
    if lay.elder is not None and data[at + lay.elder]:
        return "Esteemed Elder"
    return ""


def read_graves(game: int, data: bytes) -> list[Grave]:
    """Every grave the save holds, as the game reads them."""
    lay = LAYOUTS[game]
    if len(data) < lay.base + lay.places * lay.stride:
        raise GraveError("The save is shorter than its graves table, so its graves were not read.")
    stones: dict[int, int] = {}
    if game == 3:
        base, count, stride, _off, _cap = VV3_STONES
        for k in range(count):
            place = _i32(data, base + k * stride)
            if place >= 0:
                stones.setdefault(place, base + k * stride)
    out = []
    for place in range(lay.places):
        at = lay.base + place * lay.stride
        name = _text(data, at, lay.name_cap)
        age = _i32(data, at + lay.age)
        if game >= 3 and age == 0:
            break                               # the loader ends the list here
        if not name or (game <= 2 and age == 0):
            continue                            # an empty place
        values = {"name": name, "age": age,
                  "grave": grave_line(game, _i32(data, at + lay.job), _i32(data, at + lay.value), age)}
        if lay.epitaph:
            values["epitaph"] = _text(data, at + lay.epitaph[0], lay.epitaph[1])
        stone = stones.get(place) if game == 3 else None
        if stone is not None:
            values["epitaph"] = _text(data, stone + VV3_STONES[3], VV3_STONES[4])
        if lay.cause is not None:
            cause = _i32(data, at + lay.cause)
            values["cause"] = CAUSE_WORDS.get(cause, f"(cause {cause})")
        if lay.head is not None:
            values["head"] = _i32(data, at + lay.head)
            values["body"] = _i32(data, at + lay.body)
            values["sex"] = "Male" if data[at + lay.male] else "Female"
        if lay.elder is not None:
            values["title"] = _title_of(lay, data, at)
        fp = ln.grave_fingerprint(bytes(data[at:at + lay.name_cap]), ln.GRAVE_PRINT_CAP[game], age)
        out.append(Grave(place, at, values, fp, stone))
    return out


def graves_file(folder: Path, game: int, slot: int) -> Path | None:
    """A New Home's and The Lost Children's Graves file (VCD1): the Graves folder's, else a loose one."""
    if game > 2:
        return None
    name = f"Virtual Villagers {game} Graves - Save {slot}.dat"
    data_dir = Path(folder) / tools.DATA
    for path in (data_dir / "Graves" / name, data_dir / name):
        if path.is_file():
            return path
    return data_dir / "Graves" / name


def _vcd1_entries(data: bytes, game: int) -> list[bytearray] | None:
    if len(data) < 16 or data[:4] != b"VCD1" or _i32(data, 4) != 1 or _i32(data, 8) != game:
        return None
    count = struct.unpack_from("<I", data, 12)[0]
    if len(data) != 16 + 44 * count:
        return None
    return [bytearray(data[16 + 44 * k:16 + 44 * (k + 1)]) for k in range(count)]


def _vcd1_bytes(game: int, entries: list[bytearray]) -> bytes:
    entries = sorted(entries, key=lambda e: (struct.unpack_from("<H", e, 0)[0], struct.unpack_from("<H", e, 2)[0]))
    return struct.pack("<4sIII", b"VCD1", 1, game, len(entries)) + b"".join(bytes(e) for e in entries)


def _sidecar_values(game: int, entry: bytes) -> dict:
    out = {}
    cause = struct.unpack_from("<b", entry, 8)[0]
    if -1 <= cause <= 4:
        out["cause"] = CAUSE_WORDS[cause]
    if game == 1:
        if entry[10]:
            out["epitaph"] = _text(entry, 12, 32)
        elif 0 < entry[9] < len(EPITAPHS):
            out["epitaph"] = EPITAPHS[entry[9]]
    return out


def _load_sidecar(folder: Path, game: int, slot: int, graves: list[Grave]) -> None:
    path = graves_file(folder, game, slot)
    if path is None or not path.is_file():
        return
    entries = _vcd1_entries(path.read_bytes(), game)
    for e in entries or ():
        kind, index, fp = struct.unpack_from("<HHI", e, 0)
        if kind != 0:
            continue
        for g in graves:
            if g.place == index and g.fingerprint == fp:
                g.sidecar = _sidecar_values(game, e)


# ---------------------------------------------------------------------------
# The records
# ---------------------------------------------------------------------------

def _all_blocks(folder: Path, game: int, slot: int) -> list:
    import vv_log_additions as additions
    checker = tools.load_checker()
    villages = additions.current_villages(folder, game, slot)
    out = []
    for path in checker.log_files(Path(folder)):
        for b in additions.blocks(path):
            if b.of(slot, game, villages):
                out.append(b)
    return out


def _is_death(b) -> bool:
    return re.match(r"^Death( \d+)?$", b.heading) is not None


def _buried(b) -> bool:
    grave = b.value("Grave")
    return grave is None or not grave.startswith("no grave")


def _record_values(b) -> dict:
    out = {}
    for key, line in RECORD_LINE.items():
        v = b.value(line)
        if v is None:
            continue
        if key in ("age", "head", "body"):
            try:
                v = int(v)
            except ValueError:
                pass
        if key == "epitaph" and v == "(none)":
            v = ""
        out[key] = v
    return out


@dataclass
class Difference:
    """One field of one grave on which the sources disagree."""
    place: int
    field: str
    options: dict                   # source words -> value
    who: tuple                      # the villager (name, head, body) as the Death record names them
    text: str                       # in plain words
    choices: list = field(default_factory=list)   # the values the player may choose (the game can keep)

    @property
    def key(self) -> str:
        return f"{self.place}:{self.field}"


@dataclass
class Survey:
    game: int
    slot: int
    graves: list[Grave]
    differences: list[Difference]
    notes: list[str]
    epitaph_records: dict           # place -> the newest "Epitaph changed" block of that grave
    seen: dict = field(default_factory=dict)      # "head" / "body" -> every value this village has had


def _choices(game: int, key: str, options: dict, seen: dict) -> list:
    """The options' values the player may choose: what the grave can keep.  The job a grave shows
    comes from the villager's skills at burial, so only the record follows the grave there."""
    out = []
    for source, value in options.items():
        if key == "grave" and source != "the grave":
            continue
        try:
            value = check_value(game, key, value, seen=seen) if key != "grave" else value
        except GraveError:
            continue
        if value not in out:
            out.append(value)
    return out


def _show(value) -> str:
    if value == "" or value is None:
        return "(none)"
    return str(value)


def _pair(graves: list[Grave], deaths: list) -> tuple[dict, list, list]:
    """Each grave's Death record: the same name and age at death, in burial order; then a grave and a
    record left over that share all but one of name and age (and nothing else could be theirs)."""
    by_key: dict[tuple, list] = {}
    for b in deaths:
        by_key.setdefault((b.value("Name"), b.int_value("Age at death")), []).append(b)
    paired: dict[int, object] = {}
    used = set()
    for g in graves:
        found = by_key.get((g.name, g.age), [])
        for b in found:
            if id(b) not in used:
                paired[g.place] = b
                used.add(id(b))
                break
    left_graves = [g for g in graves if g.place not in paired]
    left_records = [b for b in deaths if id(b) not in used]
    for g in list(left_graves):
        by_name = [b for b in left_records if b.value("Name") == g.name]
        by_age = [b for b in left_records if b.int_value("Age at death") == g.age]
        for match in (by_name, by_age):
            if len(match) != 1:
                continue
            b = match[0]
            rivals = [o for o in left_graves if o is not g and (o.name == b.value("Name")
                                                                  or o.age == b.int_value("Age at death"))]
            if rivals:
                continue
            paired[g.place] = b
            left_graves.remove(g)
            left_records.remove(b)
            break
    return paired, left_graves, left_records


def _newest_epitaph(blocks: list, g: Grave, record) -> object | None:
    names = {g.name} | ({record.value("Name")} if record is not None else set())
    ages = {g.age} | ({record.int_value("Age at death")} if record is not None else set())
    found = [b for b in blocks if b.heading.startswith("Epitaph changed") and b.value("Name") in names
             and b.int_value("Age at death") in ages]
    return found[-1] if found else None


def _last_snapshot(blocks: list, who: tuple, age: int):
    """The villager's latest living record (a History or Population snapshot) at or before their age at death."""
    best = None
    for b in blocks:
        if not b.heading.startswith("Villager ") or b.identity != who:
            continue
        a = b.int_value("Age")
        if a is not None and a <= age:
            best = b
    return best


def _title_differs(game: int, grave_title: str, record_title: str | None) -> bool:
    """Whether the grave's title bytes and the record's Special villager line disagree.  Only The Secret
    City's grave keeps the Tribal Chief; a record names only the highest title, so a grave's Esteemed
    Elder agrees with any title above it (special-titles-and-masks-in-logs)."""
    record_title = record_title or ""
    if game == 3 and (grave_title == "Tribal Chief") != (record_title == "Tribal Chief"):
        return True
    if grave_title == "Tribal Chief":
        return False
    if grave_title == "Esteemed Elder":
        rank = next((k for k, t in enumerate(TITLE_RANK) if record_title.startswith(t)), None)
        return rank is None or rank > TITLE_RANK.index("Esteemed Elder")
    return record_title == "Esteemed Elder"


def survey(folder: Path, game: int, slot: int) -> Survey:
    """Every grave of the save, its Death record, and every difference between them and the patcher's
    other records.  Reads only."""
    import vv_log_decisions
    folder = Path(folder)
    data = ln.save_path(folder, game, slot).read_bytes()
    graves = read_graves(game, data)
    _load_sidecar(folder, game, slot, graves)
    blocks = _all_blocks(folder, game, slot)
    deaths = [b for b in blocks if _is_death(b) and _buried(b)]
    paired, lone_graves, lone_records = _pair(graves, deaths)
    lasts = {}
    try:
        lasts = ln.read_record(folder, game, slot)[1]
    except (OSError, ValueError, ln.LastNamesError):
        pass
    kept = {(d.get("name"), d.get("head"), d.get("body"), d.get("verdict"))
            for d in vv_log_decisions.load(folder, game, slot) if d.get("kind") == DECISION_KIND}
    seen: dict[str, set] = {"head": set(), "body": set()}
    for g in graves:
        for key in seen:
            if isinstance(g.values.get(key), int):
                seen[key].add(g.values[key])
    for b in blocks:
        for key, line in (("head", "Head"), ("body", "Body")):
            v = b.int_value(line)
            if v is not None and v >= 0:
                seen[key].add(v)
    notes: list[str] = []
    out: list[Difference] = []
    epitaphs: dict[int, object] = {}
    for g in graves:
        record = paired.get(g.place)
        g.record = record
        if record is None:
            notes.append(f"{g.label()}: no Death record. The game's grave backfill writes one from the grave.")
            continue
        rv = _record_values(record)
        who = record.identity
        newest = _newest_epitaph(blocks, g, record)
        if newest is not None:
            epitaphs[g.place] = newest
            rv["epitaph"] = (newest.value("New epitaph") or "")
            if rv["epitaph"] == "(none)":
                rv["epitaph"] = ""
        sources: dict[str, dict] = {"grave": dict(g.values)}
        for key, value in g.sidecar.items():
            sources["grave"].setdefault(key, value)
        snap = _last_snapshot(blocks, who, g.age)
        for key in FIELDS:
            gv = sources["grave"].get(key)
            r = rv.get(key)
            if key == "title":
                if gv is None or not _title_differs(game, gv, r):
                    continue
                options = {"the grave": gv, "the Death record": r or ""}
            elif key in ("custom", "mask"):
                # Kept by no grave: the record against the villager's last living snapshot.
                s = snap.value(RECORD_LINE[key]) if snap is not None else None
                if r is None or s is None or s == r:
                    continue
                options = {"the Death record": r, "their last snapshot before they died": s}
            elif gv is None or r is None or gv == r:
                continue
            elif key == "cause" and isinstance(r, str) and r.startswith(NOT_RECORDED):
                continue                        # the record says the death was not seen: nothing to choose
            elif key == "epitaph" and newest is not None:
                options = {"the grave": gv, "the newest Epitaph changed record": r}
            elif key in g.sidecar and key not in g.values:
                options = {"the patcher's Graves file": gv, "the Death record": r}
            else:
                options = {"the grave": gv, "the Death record": r}
            if any((who[0], who[1], who[2], f"{key}={_show(v)}") in kept for v in options.values()):
                notes.append(f"{g.label()}: {FIELDS[key]} differs, as you chose to leave the records.")
                continue
            parts = "; ".join(f"{src} says {_show(v)}" for src, v in options.items())
            out.append(Difference(g.place, key, options, who, f"{g.label()}: {FIELDS[key]}: {parts}.",
                                  _choices(game, key, options, seen)))
        # Mod-added: the last-names record names this villager's last name.
        first, last, number = ln.split_name(game, record.value("Name") or g.name)
        want = lasts.get((first, who[1], who[2]))
        if want is not None and last != want and len(ln.with_last(game, first, want)) <= ln.ROOM[game]:
            proposed = ln.with_last(game, record.value("Name") or g.name, want)
            options = {"the grave": g.name, "the last-names record": proposed}
            if proposed != g.name and not any(d.place == g.place and d.field == "name" for d in out) \
                    and not any((who[0], who[1], who[2], f"name={v}") in kept for v in options.values()):
                out.append(Difference(g.place, "name", options, who,
                                      f"{g.label()}: Name: the grave says {g.name}; the last-names record gives "
                                      f"this villager the last name {want} ({proposed}).",
                                      _choices(game, "name", options, seen)))
    for b in lone_records:
        notes.append(f"Death record of {b.value('Name')} (age at death {b.value('Age at death')}) names a grave "
                     "the save no longer has (the graveyard may have been full, or the save is older).")
    return Survey(game, slot, graves, out, notes, epitaphs, seen)


# ---------------------------------------------------------------------------
# Checking a new value
# ---------------------------------------------------------------------------

def editable(game: int, g: Grave | None = None) -> list[str]:
    """The fields the player may set on a grave of `game`."""
    lay = LAYOUTS[game]
    out = ["name", "age"]
    if lay.epitaph or game == 1 or (game == 3 and (g is None or g.stone is not None)):
        out.append("epitaph")
    out.append("cause")
    if lay.head is not None:
        out += ["head", "body", "sex"]
    if lay.elder is not None:
        out.append("title")
    out += ["custom", "mask"]
    return out


def check_value(game: int, key: str, value, survey_: Survey | None = None, seen: dict | None = None) -> object:
    """`value` as stored, or GraveError saying why the game could not keep it."""
    if seen is None and survey_ is not None:
        seen = survey_.seen
    if key == "name":
        value = str(value)
        if not value or len(value) > ln.ROOM[game] or not ln.storable(value):
            raise GraveError(f"A grave's name must be 1 to {ln.ROOM[game]} printable characters.")
        return value
    if key in ("age", "head", "body"):
        try:
            number = int(str(value).strip())
        except ValueError:
            raise GraveError(f"{FIELDS[key]} must be a whole number.") from None
        if key == "age" and number <= 0:
            raise GraveError("A grave's age at death must be more than 0: every game treats a grave of age 0 as "
                             "an empty place, and its next burial would take it.")
        if key == "age" and number > 100000:
            raise GraveError("That age is more than any villager lives.")
        if key in ("head", "body"):
            # A grave's looks are drawn (The Tree of Life's ghosts): only a row the game has drawn here.
            top = max(set((seen or {}).get(key, ())) | {0})
            if number < 0 or number > top:
                raise GraveError(f"{FIELDS[key]} must be one the game has drawn in this village (0 to {top}).")
        return number
    if key == "grave":
        return str(value)
    if key == "epitaph":
        value = str(value)
        if len(value) > EPITAPH_ROOM[game] or any(ord(c) < 0x20 or ord(c) > 0xFF for c in value):
            raise GraveError(f"An epitaph must be at most {EPITAPH_ROOM[game]} printable characters.")
        return value
    if key == "cause":
        if value not in CAUSE_WORDS.values():
            raise GraveError("The cause of death must be one of: " + ", ".join(CAUSE_WORDS.values()) + ".")
        return value
    if key == "sex":
        if value not in ("Male", "Female"):
            raise GraveError("Sex must be Male or Female.")
        return value
    if key == "title":
        allowed = ("", "Esteemed Elder") + (("Tribal Chief",) if game == 3 else ())
        if value not in allowed:
            raise GraveError("A grave keeps only " + " or ".join(a or "no title" for a in allowed) + ".")
        return value
    if key in ("custom", "mask"):
        value = str(value).strip()
        if any(ord(c) < 0x20 or ord(c) > 0xFF for c in value) or len(value) > 60:
            raise GraveError(f"{FIELDS[key]} must be at most 60 printable characters.")
        return value
    raise GraveError(f"{key} is not a grave field.")


# ---------------------------------------------------------------------------
# Planning the changes
# ---------------------------------------------------------------------------

@dataclass
class Fix:
    place: int
    field: str
    value: object
    who: tuple = ()
    old: object = None


class _Lines:
    """A log file's lines, changed in place; the byte offsets of the unchanged text are followed."""

    def __init__(self, path: Path):
        self.path = path
        self.original = path.read_bytes()
        self.crlf = b"\r\n" in self.original
        self.lines = self.original.decode("latin-1").replace("\r\n", "\n").split("\n")
        self.head: dict[int, str | None] = {}      # a line replaced (None: taken out)
        self.extra: dict[int, list[str]] = {}      # lines added after it
        self.count = 0

    def set(self, index: int, text: str | None) -> None:
        self.head[index] = text
        self.count += 1

    def insert_after(self, index: int, text: str) -> None:
        self.extra.setdefault(index, []).append(text)
        self.count += 1

    def _now(self, i: int) -> list[str]:
        first = self.head.get(i, self.lines[i])
        return ([] if first is None else [first]) + self.extra.get(i, [])

    def render(self) -> bytes:
        out = []
        for i in range(len(self.lines)):
            out += self._now(i)
        text = "\n".join(out)
        if self.crlf:
            text = text.replace("\n", "\r\n")
        return text.encode("latin-1")

    def moved(self, offset: int) -> int:
        nl = 2 if self.crlf else 1
        old = new = 0
        for i, line in enumerate(self.lines):
            length = len(line.encode("latin-1")) + nl
            now = self._now(i)
            now_length = sum(len(t.encode("latin-1")) + nl for t in now)
            if offset < old + length:
                return new + min(offset - old, now_length)
            old += length
            new += now_length
        return new + (offset - old)


@dataclass
class Plan:
    changes: list
    fixes: list[Fix]
    docs: list = field(default_factory=list)
    decisions: list = field(default_factory=list)
    in_save: int = 0                # fields written into the save
    village: str | None = None      # the "Village: <name> (Save n)" the records are under


def _set_text(buf: bytearray, at: int, cap: int, text: str) -> None:
    encoded = text.encode("latin-1")
    if len(encoded) >= cap:
        raise GraveError(f"{text!r} does not fit its {cap}-byte field.")
    buf[at:at + cap] = encoded + bytes(cap - len(encoded))


def _apply_to_save(game: int, buf: bytearray, g: Grave, key: str, value) -> bool:
    """Write one field into the grave in `buf`.  False: the grave does not keep it."""
    lay = LAYOUTS[game]
    at = g.at
    if key == "name":
        _set_text(buf, at, lay.name_cap, value)
    elif key == "age":
        struct.pack_into("<i", buf, at + lay.age, value)
        if lay.child is not None:
            buf[at + lay.child] = 1 if value < CHILD_AGE else 0
    elif key == "epitaph":
        if game == 3:
            if g.stone is None:
                return False
            _set_text(buf, g.stone + VV3_STONES[3], VV3_STONES[4], value)
        elif lay.epitaph:
            _set_text(buf, at + lay.epitaph[0], lay.epitaph[1], value)
        else:
            return False
    elif key == "cause":
        if lay.cause is None:
            return False
        code = next(k for k, v in CAUSE_WORDS.items() if v == value)
        struct.pack_into("<i", buf, at + lay.cause, code)
    elif key in ("head", "body"):
        if lay.head is None:
            return False
        struct.pack_into("<i", buf, at + (lay.head if key == "head" else lay.body), value)
    elif key == "sex":
        if lay.male is None:
            return False
        buf[at + lay.male] = 1 if value == "Male" else 0
    elif key == "title":
        if lay.elder is None:
            return False
        if lay.chief is not None:
            buf[at + lay.chief] = 1 if value == "Tribal Chief" else 0
        buf[at + lay.elder] = 1 if value == "Esteemed Elder" else 0
    else:
        return False
    return True


def _plan_sidecar(folder: Path, game: int, slot: int, by_place: dict, rekey: dict, changes: list) -> None:
    """The Graves file (A New Home, The Lost Children): a changed cause or epitaph, and every entry of a
    renamed or re-aged grave given its new fingerprint; Graves Logged (every game) re-keyed."""
    path = graves_file(folder, game, slot)
    if path is not None and (rekey or by_place):
        original = path.read_bytes() if path.is_file() else None
        entries = _vcd1_entries(original, game) if original is not None else []
        if entries is None:
            raise GraveError(f"{path.name} could not be read, so it was not changed (nothing was).")
        touched = False
        # The cause and epitaph first, on the entry under the grave's fingerprint as it was; then
        # every entry of a renamed or re-aged grave given the new one.
        for place, (fp, values) in by_place.items():
            mine = [e for e in entries if struct.unpack_from("<HHI", e, 0) == (0, place, fp)]
            if not mine:
                e = bytearray(44)
                struct.pack_into("<HHIb", e, 0, 0, place, fp, CAUSE_NONE)
                entries.append(e)
                mine = [e]
            e = mine[0]
            if "cause" in values:
                struct.pack_into("<b", e, 8, next(k for k, v in CAUSE_WORDS.items() if v == values["cause"]))
            if "epitaph" in values and game == 1:
                text = values["epitaph"]
                if text in EPITAPHS[1:]:
                    e[9], e[10] = EPITAPHS.index(text), 0
                    e[12:44] = bytes(32)
                else:
                    e[9], e[10] = 0, 1
                    e[12:44] = text.encode("latin-1") + bytes(32 - len(text))
            touched = True
        for place, (old_fp, new_fp) in rekey.items():
            for e in entries:
                kind, index, fp = struct.unpack_from("<HHI", e, 0)
                if kind == 0 and index == place and fp == old_fp:
                    struct.pack_into("<I", e, 4, new_fp)
                    touched = True
        if touched:
            updated = _vcd1_bytes(game, entries)
            if updated != original:
                changes.append(ln.Change(path, original, updated, "the Graves file"))
    logged = Path(folder) / tools.DATA / "Deaths" / f"Virtual Villagers {game} Graves Logged - Save {slot}.dat"
    if rekey and logged.is_file():
        original = logged.read_bytes()
        checker = tools.load_checker()
        if checker.graves_logged_problem(original, game) is None:
            data = bytearray(original)
            count = struct.unpack_from("<I", data, 12)[0]
            for k in range(count):
                place, _pad, fp = struct.unpack_from("<HHI", data, 16 + 8 * k)
                if place in rekey and fp == rekey[place][0]:
                    struct.pack_into("<I", data, 16 + 8 * k + 4, rekey[place][1])
            if bytes(data) != original:
                changes.append(ln.Change(logged, original, bytes(data), "the Graves Logged file"))


def _record_edits(docs: dict, record, key: str, value, epitaph_record=None) -> None:
    """The Death record's line for `key` (or the newest Epitaph changed record's New epitaph) set to `value`."""
    shown = _show(value) if key in ("epitaph", "custom", "mask", "title") else str(value)
    target = record
    line = RECORD_LINE[key]
    if key == "epitaph" and epitaph_record is not None:
        target, line = epitaph_record, "New epitaph"
    doc = docs.setdefault(target.path, _Lines(target.path))
    index = target.index_of(line)
    if key in ("title", "custom", "mask") and value == "":
        if index is not None:
            doc.set(index, None)
        return
    if index is not None:
        doc.set(index, f"  {line}: {shown}")
        return
    for after in INSERT_AFTER.get(key, ("Name",)):
        anchor = target.index_of(after)
        if anchor is not None:
            doc.insert_after(anchor, f"  {line}: {shown}")
            return
    doc.insert_after(target.start, f"  {line}: {shown}")


def plan(folder: Path, game: int, slot: int, fixes: list[Fix], retro: bool,
         surveyed: Survey | None = None) -> Plan:
    """What setting each grave field in `fixes` changes, file by file.  Reads only.  With `retro`
    ("Retroactively edit records?" Yes) the Death records follow; without, only the save and the
    patcher's grave files do, and each decision is kept so it is not asked again."""
    folder = Path(folder)
    work = surveyed or survey(folder, game, slot)
    graves = {g.place: g for g in work.graves}
    save = ln.save_path(folder, game, slot)
    original = save.read_bytes()
    buf = bytearray(original)
    changes: list = []
    by_place: dict[int, tuple] = {}
    rekey: dict[int, tuple] = {}
    docs: dict[Path, _Lines] = {}
    decisions = []
    done: list[Fix] = []
    written = 0
    for fix in fixes:
        g = graves.get(fix.place)
        if g is None:
            raise GraveError(f"Grave {fix.place + 1} is no longer in the save; nothing was changed.")
        value = check_value(game, fix.field, fix.value, work)
        if fix.field == "grave" and value != g.values["grave"]:
            raise GraveError(f"{g.label()}: the job a grave shows comes from the villager's skills when they "
                             "were buried, so only the Death record can be made to match the grave.")
        if fix.field in ("custom", "mask") and g.record is None:
            raise GraveError(f"{g.label()} has no Death record to hold a {FIELDS[fix.field]}.")
        fix = Fix(fix.place, fix.field, value, fix.who or (g.record.identity if g.record is not None else ()),
                  g.values.get(fix.field, g.sidecar.get(fix.field)) if fix.field not in ("custom", "mask")
                  else (g.record.value(RECORD_LINE[fix.field]) or ""))
        in_save = _apply_to_save(game, buf, g, fix.field, value)
        written += in_save
        if not in_save and fix.field in ("cause", "epitaph") and game <= 2:
            fp, values = by_place.get(g.place, (g.fingerprint, {}))
            values[fix.field] = value
            by_place[g.place] = (fp, values)
        if fix.field in ("name", "age"):
            lay = LAYOUTS[game]
            new_fp = ln.grave_fingerprint(bytes(buf[g.at:g.at + lay.name_cap]), ln.GRAVE_PRINT_CAP[game],
                                          _i32(buf, g.at + lay.age))
            rekey[g.place] = (g.fingerprint, new_fp)
        if g.record is not None and retro:
            _record_edits(docs, g.record, fix.field, value, work.epitaph_records.get(g.place))
            if fix.field in ("name", "age"):
                for b in _epitaph_blocks(folder, game, slot, g):
                    doc = docs.setdefault(b.path, _Lines(b.path))
                    line = RECORD_LINE[fix.field]
                    index = b.index_of(line)
                    if index is not None:
                        doc.set(index, f"  {line}: {value}")
        elif g.record is not None:
            who = g.record.identity
            decisions.append({"kind": DECISION_KIND, "village": g.record.village, "name": who[0], "head": who[1],
                              "body": who[2], "verdict": f"{fix.field}={_show(value)}", "edited": False})
        done.append(fix)
    if bytes(buf) != original:
        changes.append(ln.Change(save, original, bytes(buf), "the save"))
    _plan_sidecar(folder, game, slot, by_place, rekey, changes)
    for path, doc in docs.items():
        updated = doc.render()
        if updated != doc.original:
            changes.append(ln.Change(path, doc.original, updated, "the logs"))
    village = next((g.record.village for g in work.graves if g.record is not None and g.record.village), None)
    return Plan(changes, done, list(docs.values()), decisions, written, village)


def _epitaph_blocks(folder: Path, game: int, slot: int, g: Grave) -> list:
    return [b for b in _all_blocks(folder, game, slot) if b.heading.startswith("Epitaph changed")
            and b.value("Name") == g.name and b.int_value("Age at death") == g.age]


# ---------------------------------------------------------------------------
# Applying
# ---------------------------------------------------------------------------

@dataclass
class Result:
    fixes: list[Fix]
    files: list[Path]
    backup: object
    kept: int                       # decisions remembered without editing the records


@dataclass
class _Applied:
    files: list[Path]
    backup: object


def _apply(folder: Path, changes: list, controller, now: datetime | None) -> _Applied:
    """vv_last_names.apply's safety, with a file that did not exist yet (the Graves file of a village
    that had none): the save folder backed up first, refused while the game runs, every file swapped
    in and read back, every one put back -- a new one taken away -- on a failure."""
    try:
        backup = vv_save_backup.copy_save_folder(folder, now or datetime.now(), suffix=BACKUP_LABEL)
    except vv_save_backup.BackupError as exc:
        raise GraveError(f"The backup failed, so nothing was changed. {exc}") from exc
    tools._refuse_if_running(folder, controller)
    done: list = []
    try:
        for change in changes:                  # original None: a file made new
            current = change.path.read_bytes() if change.path.is_file() else None
            if current != change.original:
                raise GraveError(f"{change.path.name} changed while the graves were being fixed.")
            done.append((change, current is not None))
            change.path.parent.mkdir(parents=True, exist_ok=True)
            ln._write(change.path, change.updated)
    except (OSError, GraveError, ln.LastNamesError) as exc:
        problems = []
        for change, existed in reversed(done):
            try:
                if existed:
                    if change.path.read_bytes() != change.original:
                        ln._write(change.path, change.original)
                elif change.path.exists():
                    change.path.unlink()
            except (OSError, ln.LastNamesError) as undo:
                problems.append(f"{change.path.name}: {undo}")
        if problems:
            raise GraveError(f"Fixing the graves failed ({exc}) and these files could not be put back: "
                             f"{'; '.join(problems)}. Your backup is in {backup.backup_folder}.") from exc
        raise GraveError(f"Fixing the graves failed ({exc}); every file was put back as it was. "
                         f"A backup is in {backup.backup_folder}.") from exc
    return _Applied([c.path for c in changes], backup)


def fix_graves(folder: Path, game: int, slot: int, fixes: list[Fix], retro: bool,
               processes: vv_save_backup.ProcessController | None = None,
               now: datetime | None = None) -> Result:
    """Set the chosen grave fields.  Refused (nothing changed) while the game runs; the save folder is
    backed up first, each file copied into Copies Made Before Repairs; any failure puts every changed
    file back; a Repair record goes into the Repairs Made log."""
    import vv_log_decisions
    folder = Path(folder)
    controller = processes if processes is not None else vv_save_backup.WindowsProcesses()
    tools._refuse_if_running(folder, controller)
    if not fixes:
        raise GraveError("No grave information was chosen to change.")
    try:
        work = plan(folder, game, slot, fixes, retro)
    except (struct.error, ValueError, OSError) as exc:
        raise GraveError(f"A file could not be read ({exc}); nothing was changed.") from exc
    copies = []
    for change in work.changes:
        if change.original is None:
            continue
        for k in range(1, 1000):
            target = tools.copy_before_repair(folder, change.path, COPY_SUFFIX + ("" if k == 1 else f"-{k}"))
            if not target.exists():
                break
        else:
            raise GraveError(f"{change.path.name} has too many copies already; nothing was changed.")
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "xb") as copy:
            copy.write(change.original)
        copies.append((change, target))
    applied = _apply(folder, work.changes, controller, now)
    for doc in work.docs:
        named = re.match(r"^Virtual Villagers (\d) ", doc.path.name)
        if named and doc.render() != doc.original:
            try:
                tools.move_word_boundary(folder, doc.path, int(named.group(1)), doc.moved)
            except (OSError, ValueError):
                pass
    if work.decisions:
        vv_log_decisions.record(folder, game, slot, work.decisions, now)
    village = work.village
    counts: dict[Path, int] = {ln.save_path(folder, game, slot): work.in_save}
    for doc in work.docs:
        counts[doc.path] = doc.count
    entries = [tools.WordFix(str(c.path.relative_to(folder)), counts.get(c.path, 1), target.name)
               for c, target in copies]
    entries += [tools.WordFix(str(c.path.relative_to(folder)), 1, "(a new file)") for c in work.changes
                if c.original is None]
    tools.note_word_repair(folder, game, village, entries, now,
                           checked="each grave against its Death record and the patcher's grave files, "
                                   "with the player's choices (" + "; ".join(describe(f) for f in work.fixes) + ")"
                                   + ("" if retro else "; the old records were left as they were"),
                           corrected="Grave information corrected", unit="field(s)")
    return Result(work.fixes, applied.files, applied.backup, len(work.decisions))


def describe(fix: Fix) -> str:
    who = fix.who[0] if fix.who else f"grave {fix.place + 1}"
    return f"{who}: {FIELDS[fix.field]} {_show(fix.old)} -> {_show(fix.value)}"
