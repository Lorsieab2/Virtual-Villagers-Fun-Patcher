"""Give a village's villagers last names, in the game and in the logs (all five games).

The owner (2026-10-06): Repair Saves & Logs may add the unused Last Names to villagers
who already have names -- "Rename in game + logs": with the game closed, each
living villager the player chooses gets " <last name>" after their name in the
save AND in every log, so the logs keep matching the save; the player picks
each last name from the game's own list (the family's by default: family
1..50 is name number family - 1, as Villagers Have Last Names gives new
villagers) or types one ("The player can type in a name or choose from the
default lists").

A name is more than the save's own field.  Everything the patcher keeps that
holds a villager's name, or a hash of it, follows (the inventory, PR #553):

  the save        the villager's name; in The Lost Children to New Believers
                  each child's father / mother name fields, and a pregnant
                  mother's father-of-the-baby field, that name them
  masks           every game's Village Masks file: its stored identities
  custom titles   Custom Titles - Save N.dat: each title's identity
  former Heathens New Believers' Former Heathens file: each identity
  A New Home      its Parentage Records file: the roster's names and every
                  father / mother / expected-father name
  Unaccounted     the Village Roster the Unaccounted Villagers log is
                  reconciled against: the names inside each snapshot
  statistics      Village Statistics' Village Roster and the Village Elders
                  file: the names on their lines
  the logs        every record of the villager -- their own "Name:" lines and
                  every Child / Mother / Father line naming them -- by name,
                  head and body

A villager is told apart by name, head and body.  When two living villagers
share all three, they are given the same last name (the logs cannot tell
which record is whose), and a dead villager whose records share them is
asked about (src/vv_log_additions.py's questions).  Only living villagers
are renamed: a grave keeps the name it was dug with.

Safety (as Rename Tribe): the game must be closed; the save folder is backed
up first ("(before last names)"); every file is written through a temporary
file, swapped in and read back; any failure puts every changed file back.
"""
from __future__ import annotations

import os
import random
import re
import struct
import zlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import vv_log_tools as tools
import vv_save_backup
import vv_save_layout as layout

BACKUP_LABEL = "(before last names)"
FNV_BASIS, FNV_PRIME = 2166136261, 16777619

# The longest name each game may be given: its own name field less the
# terminator, within the bound the game's own villager copy uses (A New Home
# 28 bytes; The Lost Children 24; the later games 24 of a 25-byte field).
ROOM = {1: 27, 2: 23, 3: 23, 4: 23, 5: 23}


class LastNamesError(Exception):
    """Nothing was changed (or everything was put back); the message says why."""


@dataclass(frozen=True)
class Fields:
    """Offsets relative to the villager's name inside a saved entry."""
    name_cap: int
    family: int
    sex: int
    male: int
    head: int
    body: int
    father: int | None
    mother: int | None
    expecting: int | None           # the mother's father-of-the-baby name
    parent_cap: int
    likes: int
    dislikes: int
    slots: int                      # likes / dislikes dwords
    looks: tuple = ()               # (father head, body, mother head, body, expecting head, body)


FIELDS = {
    # A New Home: the record window +0x33C..+0x3D8, the name at +0x370.
    1: Fields(0x1C, 0x36C - 0x370, 0x350 - 0x370, 1, 0x360 - 0x370, 0x364 - 0x370,
              None, None, None, 0, 0x398 - 0x370, 0x3A8 - 0x370, 4),
    2: Fields(0x18, 0x554 - 0x564, 0x538 - 0x564, 1, 0x548 - 0x564, 0x54C - 0x564,
              0x19, 0x32, 0x5C0 - 0x564, 0x18, 0x5F0 - 0x564, 0x6E8 - 0x564, 62,
              (0x5B0 - 0x564, 0x5B4 - 0x564, 0x5B8 - 0x564, 0x5BC - 0x564, 0x5E0 - 0x564, 0x5DC - 0x564)),
    # The Secret City: windows (0xDC4,0xA8) +4, (0xE6C,0x40) +0xAC, (0xEAC,0x18) +0xEC,
    # (0xFB4,0xC) +0x104, (0xFC0,0xC) +0x110; the name at entry +0x14.
    3: Fields(0x19, -4, -0x0C, 0, 0x1C, 0x20, 0x24, 0x3D, 0x74, 0x19, 0x104 - 0x14, 0x110 - 0x14, 3,
              (0x58, 0x5C, 0x60, 0x64, 0x94, 0x90)),
    # The Tree of Life: (0x1B8C,0xA8) +4, (0x1C34,0x28) +0xAC, (0x1C5C,0x18) +0xD4,
    # (0x1E60,0x18) +0xEC; the name at entry +0x14.
    4: Fields(0x19, -4, -0x0C, 0, 0x1C, 0x20, 0x24, 0x3D, 0x74, 0x19, 0xEC - 0x14, 0xF8 - 0x14, 3,
              (0x58, 0x5C, 0x60, 0x64, 0x94, 0x90)),
    # New Believers (its writer 0x465270): a 0x10 header, (0x1B8C,0xA8) +0x10, ..., the
    # likes and dislikes +0xFC..+0x110; the name at entry +0x20.
    5: Fields(0x19, -4, -0x0C, 0, 0x1C, 0x20, 0x24, 0x3D, 0x74, 0x19, 0xFC - 0x20, 0x108 - 0x20, 3,
              (0x58, 0x5C, 0x60, 0x64, 0x94, 0x90)),
}

# Each game's graves in the save file (the owner, 2026-10-07: renames "should be retroactive too! (in
# logs, saves, graves, etc)"): (file offset, slots, stride, name field bytes, age-at-death offset,
# (head, body) offsets or None).  The game copies a villager's name there at burial; The Secret City,
# The Tree of Life and New Believers refuse a whole save whose grave name has no NUL in its first
# 0x19 bytes, so a new name is always written NUL-terminated and zero-filled within its field.
GRAVES = {
    1: (0xA320, 50, 0x2C, 0x1C, 0x24, None),        # manager +0xA31C (cod_vv12.inc)
    2: (0x2EB10, 50, 0x7C, 0x19, 0x74, None),       # world +0x2EB0C; the epitaph follows the name
    3: (0xF0C, 500, 0x30, 0x19, 0x1C, None),        # the Roster of the Dead (writer 0x454FF0)
    4: (0x908, 500, 0x5C, 0x19, 0x1C, (0x20, 0x24)),  # writer 0x45D470
    5: (0x86C, 500, 0x5C, 0x19, 0x1C, (0x20, 0x24)),  # writer 0x464C70
}
# The bytes of the name the cause-of-death fingerprint reads (cod_fingerprint, its `cap`).
GRAVE_PRINT_CAP = {1: 0x1C, 2: 0x18, 3: 0x19, 4: 0x19, 5: 0x19}


def grave_fingerprint(name: bytes, cap: int, age: int) -> int:
    """cod_fingerprint (native/vvfp_cause_of_death/vvfp_cause_of_death.c): the name to its NUL or
    `cap` bytes, 0xFF, then the age at death's four bytes."""
    h = _fnv(FNV_BASIS, name.split(b"\0", 1)[0][:cap])
    h = _fnv(h, b"\xff")
    h = _fnv(h, struct.pack("<i", age))
    return h or 1


def _rename_graves(buf: bytearray, game: int, renames: dict[tuple, str], ages: dict[tuple, int],
                   result) -> list[tuple[int, bytes, bytes, int]]:
    """Each renamed dead villager's grave, matched by name and age at death (and looks, where the game
    keeps them on the grave): renamed in `buf`.  An unclear match is left alone and reported.  Returns
    (place, old name, new name, age) for each grave renamed."""
    base, slots, stride, cap, age_at, looks = GRAVES[game]
    if len(buf) < base + slots * stride:
        return []
    graves = []
    for i in range(slots):
        at = base + i * stride
        name = _cstr(buf, at, cap)
        if not name:                            # an empty place (a baby may die at age 0)
            continue
        graves.append((i, at, name, _i32(buf, at + age_at),
                       (_i32(buf, at + looks[0]), _i32(buf, at + looks[1])) if looks else None))
    done = []
    for (name, head, body), new in renames.items():
        age = ages.get((name, head, body))
        if age is None:
            continue
        # A grave dug before the logs were renamed (last names given by an earlier build) still carries
        # the game's own first name.
        on_grave = name
        found = [g for g in graves if g[2] == name and g[3] == age and (g[4] is None or g[4] == (head, body))]
        if not found:
            on_grave = split_name(game, name)[0]
            found = [g for g in graves if g[2] == on_grave != name and g[3] == age
                     and (g[4] is None or g[4] == (head, body))]
        rivals = [key for key in ages if key != (name, head, body) and ages[key] == age
                  and on_grave in (key[0], split_name(game, key[0])[0])]
        if len(found) != 1 or (looks is None and rivals):
            if found:
                result.notes.append(f"The grave of {name} (age {age}) could be more than one villager's, so it "
                                    "keeps its name.")
            continue
        encoded = new.encode("latin-1", "replace")
        if len(encoded) > cap - 1:
            result.notes.append(f"{new} is too long for {name}'s grave, which keeps its name.")
            continue
        place, at, _old, _age, _looks = found[0]
        old = bytes(buf[at:at + cap])
        buf[at:at + cap] = encoded + bytes(cap - len(encoded))
        done.append((place, old, encoded, age))
    return done


def _plan_grave_files(result, folder: Path, game: int, slot: int, renamed: list) -> None:
    """The cause-of-death files that know a grave by its name-and-age fingerprint: the Graves file
    (A New Home, The Lost Children: cause and epitaph) and Graves Logged (every game: which graves
    have their Death record), so nothing drifts or is filed twice."""
    if not renamed:
        return
    cap = GRAVE_PRINT_CAP[game]
    moved = {(place, grave_fingerprint(old, cap, age)): grave_fingerprint(new, cap, age)
             for place, old, new, age in renamed}
    data_dir = Path(folder) / tools.DATA
    graves_name = f"Virtual Villagers {game} Graves - Save {slot}.dat"
    for path, magic, header, size, place_kind in (
            (data_dir / "Graves" / graves_name, b"VCD1", 16, 44, True),
            (data_dir / graves_name, b"VCD1", 16, 44, True),
            (data_dir / "Deaths" / f"Virtual Villagers {game} Graves Logged - Save {slot}.dat", b"VCG1", 16, 8, False)):
        if not path.is_file() or (magic == b"VCD1" and game > 2):
            continue
        original = path.read_bytes()
        if len(original) < header or original[:4] != magic or _i32(original, 8) != game:
            continue
        count = struct.unpack_from("<I", original, 12)[0]
        if len(original) != header + size * count:
            continue
        data = bytearray(original)
        for k in range(count):
            e = header + size * k
            if place_kind:                      # VCD1: u16 kind (0 grave), u16 index, u32 fingerprint
                kind, place, fp = struct.unpack_from("<HHI", data, e)
                if kind != 0:
                    continue
            else:                               # VCG1: u16 place, u16 0, u32 fingerprint
                place, _pad, fp = struct.unpack_from("<HHI", data, e)
            new = moved.get((place, fp))
            if new is not None:
                struct.pack_into("<I", data, e + 4, new)
        if bytes(data) != original:
            result.changes.append(Change(path, original, bytes(data), "the graves' cause-of-death files"))


def _death_ages(folder: Path, game: int, slot: int) -> dict[tuple, int]:
    """Each dead villager's age at death, by (name, head, body), from the Deaths log."""
    import vv_log_additions as additions
    out = {}
    for b in additions.person_blocks(folder, slot, game):
        if not b.heading.startswith("Death"):
            continue
        age = b.value("Age at death")
        name, head, body = b.identity
        if name and head is not None and body is not None and age and age.lstrip("-").isdigit():
            out[(name, head, body)] = int(age)
    return out


# The villager record's own offsets (for the Unaccounted roster's snapshots).
RECORD = {
    1: {"name": 0x370, "head": 0x360, "body": 0x364},
    2: {"name": 0x564, "head": 0x548, "body": 0x54C,
        "father": (0x57D, 0x5B0, 0x5B4), "mother": (0x596, 0x5B8, 0x5BC), "expecting": (0x5C0, 0x5E0, 0x5DC)},
    3: {"name": 0xDD4, "head": 0xDF0, "body": 0xDF4,
        "father": (0xDF8, 0xE2C, 0xE30), "mother": (0xE11, 0xE34, 0xE38), "expecting": (0xE48, 0xE68, 0xE64)},
    4: {"name": 0x1B9C, "head": 0x1BB8, "body": 0x1BBC,
        "father": (0x1BC0, 0x1BF4, 0x1BF8), "mother": (0x1BD9, 0x1BFC, 0x1C00), "expecting": (0x1C10, 0x1C30, 0x1C2C)},
    5: {"name": 0x1B9C, "head": 0x1BB8, "body": 0x1BBC,
        "father": (0x1BC0, 0x1BF4, 0x1BF8), "mother": (0x1BD9, 0x1BFC, 0x1C00), "expecting": (0x1C10, 0x1C30, 0x1C2C)},
}


def _fnv(h: int, data: bytes) -> int:
    for b in data:
        h = ((h ^ b) * FNV_PRIME) & 0xFFFFFFFF
    return h


def _cstr(data: bytes | bytearray, at: int, cap: int) -> str:
    return bytes(data[at:at + cap]).split(b"\0", 1)[0].decode("latin-1")


def _i32(data, at: int) -> int:
    return struct.unpack_from("<i", data, at)[0]


@dataclass
class Living:
    """A living villager in the save, where its name is."""
    at: int                         # the name's offset in the save file
    name: str
    sex: str
    head: int
    body: int
    family: int
    default: str                    # the family's last name, or "" outside 1..50
    alive: bool = True              # False: dead, disappeared or gone, known from the logs only (at -1)
    arrived: bool = False           # came through an event, not a founder (everyone(): ARRIVALS)

    @property
    def identity(self) -> tuple:
        return (self.name, self.head, self.body)


def save_path(folder: Path, game: int, slot: int) -> Path:
    checker = tools.load_checker()
    return Path(folder) / f"{checker.SAVE_STEMS[game]}{slot}.ldw"


def _entries(game: int, data: bytes, bodies: bool = False) -> list[int]:
    """The name offset of every villager the game loads from the save (the checker's own reading:
    the records up to the first one not flagged present; the stale copies after it are never
    loaded, scripts/vvfp_consistency_check.py PRESENT).  With `bodies`, the unburied dead too
    (Number Duplicate Names renames a dead namesake's body, Codex #557)."""
    checker = tools.load_checker()
    if game == 1:
        out = []
        for i in range(256):
            base = checker.VV1_BLOCK0 + i * checker.VV1_STRIDE
            rel = lambda off: base + off - checker.VV1_BASE  # noqa: E731
            if data[rel(0x3D4)] != 1:                 # the byte: its dword can be 0x011C0001
                break
            name = _cstr(data, rel(0x370), 0x1B)
            if name and _i32(data, rel(0x350)) in (1, 2) \
                    and (bodies or _i32(data, rel(0x344)) > 0):   # a body keeps the name it died with
                out.append(rel(0x370))
        return out
    try:
        offsets = checker.villager_offsets(game, data, [])
    except ValueError:
        raise LastNamesError("The save's villager table was not found.") from None
    # Living villagers only, unless `bodies`: never a statue; a body's name is the one it died with.
    return [p for p in offsets if not checker.lookalike(data, p, game)
            and (bodies or _i32(data, p + checker.HEALTH[game]) > 0)]


def living(folder: Path, game: int, slot: int, bodies: bool = False) -> list[Living]:
    """The save's living villagers (and, with `bodies`, its unburied dead), with each one's family
    last name."""
    checker = tools.load_checker()
    data = save_path(folder, game, slot).read_bytes()
    f = FIELDS[game]
    names = checker.LAST_NAMES[game]
    out = []
    for at in _entries(game, data, bodies):
        family = _i32(data, at + f.family)
        out.append(Living(at, _cstr(data, at, f.name_cap), "Male" if _i32(data, at + f.sex) == f.male else "Female",
                          _i32(data, at + f.head), _i32(data, at + f.body), family,
                          names[family - 1] if 1 <= family <= 50 else ""))
    return out


# Where a villager's last name comes from (the owner, 2026-10-07: "an option to choose whether
# people inherit the Father or Mother's last name, or random 50:50 or player choice for each
# villager").
INHERIT = {
    "mother": "From the mother",
    "father": "From the father",
    "random": "Equal mother/father (50:50)",
    "list": "Random from list",
    "each": "Choose from list",
}
# The rules where the player gives each villager's last name: a villager keeps the one they carry
# until the player changes it, so choosing the rule never wipes a name.
PLAYER_RULES = ("each",)
# The entry in each villager's own list for typing a last name of the player's own (the owner,
# 2026-10-07: "IN THE LIST THERE SHOULD BE A (CUSTOM LAST NAME - TYPE HERE...) ENTRY").
CUSTOM = "(custom last name - type here...)"


def own_last_name(name: str) -> str:
    """The last name a villager's name already carries (after its last space), or ""."""
    return name.rpartition(" ")[2] if " " in name else ""


NUMERAL = re.compile(r"^[IVXLCDM]+$")


def storable(name: str) -> bool:
    """A name the games keep and show safely: printable ASCII or a Latin-1 letter or sign the game's
    own text box accepts (Élodie; Codex, #566) -- never a control byte, and never '%', which an
    unpatched game reads as a formatting instruction (Fix Vanilla Bugs)."""
    return all((0x20 <= ord(ch) < 0x7F or 0xA0 <= ord(ch) <= 0xFF) and ch != "%" for ch in name)
# In a `known` set: a name (without its numeral) whose words are all one first name -- the owner,
# 2026-10-07, for a two-word name whose second word is no known last name: "Ask per villager".
WHOLE = "\0whole\t"


def guessed_last_name(game: int, name: str, known: set[str] | frozenset = frozenset()) -> str:
    """The last name `name` is only taken to carry because its second word is no first name -- not
    one of the game's list or the village's record ("Chapa Chapstick" typed in v1.35.62, or "Big
    Bob" set with Cheat Engine): the player is asked.  "" when there is nothing to ask."""
    plain = {n for n in known if not n.startswith(WHOLE)}
    last = split_name(game, name, plain)[1]
    return "" if not last or last in plain or last in tools.load_checker().LAST_NAMES[game] else last


def split_name(game: int, name: str, known: set[str] | frozenset = frozenset()) -> tuple[str, str, str]:
    """(first, last, suffix): a name's own part, its last name -- one of the game's list, or one the
    player gave (`known`, the village's record) -- and what follows it (Number Duplicate Names'
    numeral: "Soda Akikai II").  A first word is never a last name.  The game's own names are one
    word, so any later word that is not a numeral is a last name too -- one typed in v1.35.62, before
    the village kept a record ("Chapa Chapstick"), is never given a second last name."""
    words = name.split(" ")
    k = len(words) - 1
    while k > 0 and NUMERAL.match(words[k]):
        k -= 1
    base = " ".join(words[:k + 1])
    if WHOLE + base in known:                   # the player: these words are one first name
        return base, "", " ".join(words[k + 1:])
    names = set(tools.load_checker().LAST_NAMES[game]) | set(known)
    for k in range(len(words) - 1, 0, -1):
        if words[k] in names:
            return " ".join(words[:k]), words[k], " ".join(words[k + 1:])
    k = len(words) - 1
    while k > 0 and NUMERAL.match(words[k]):
        k -= 1
    if k > 0:
        return " ".join(words[:k]), words[k], " ".join(words[k + 1:])
    if len(words) > 1:
        return words[0], "", " ".join(words[1:])
    return name, "", ""


def with_last(game: int, name: str, last: str, known: set[str] | frozenset = frozenset()) -> str:
    """`name` with its last name replaced by `last` ("" none), any numeral kept after it."""
    first, _old, suffix = split_name(game, name, known)
    return " ".join(word for word in (first, last, suffix) if word)


def record_path(folder: Path, game: int, slot: int) -> Path:
    return Path(folder) / tools.DATA / "Last Names" / f"Virtual Villagers {game} Last Names - Save {slot}.dat"


RECORD_HEADER = "VVFP LAST NAMES v1 game={game}"


def read_record(folder: Path, game: int, slot: int) -> tuple[str | None, dict[tuple, str]]:
    """The village's last-name record: the rule last used, and the last names the player gave
    villagers themselves, by (first name, head, body) -- so a later check knows what "right" is (the
    owner, 2026-10-07: "implement a check for "Wrong last names"").  (None, {}) without one."""
    try:
        lines = record_path(folder, game, slot).read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return None, {}
    if not lines or lines[0] != RECORD_HEADER.format(game=game):
        return None, {}
    rule, fixed = None, {}
    for line in lines[1:]:
        parts = line.split("\t")
        if parts[0] == "rule" and len(parts) == 2 and parts[1] in INHERIT:
            rule = parts[1]
        elif parts[0] == "set" and len(parts) == 5 and parts[2].lstrip("-").isdigit() and parts[3].lstrip("-").isdigit():
            fixed[(parts[1], int(parts[2]), int(parts[3]))] = parts[4]
    return rule, fixed


def read_whole(folder: Path, game: int, slot: int) -> set[str]:
    """The names the player said are one first name, not a first and a last ("whole" lines; a
    reader that does not know them skips them)."""
    try:
        lines = record_path(folder, game, slot).read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return set()
    if not lines or lines[0] != RECORD_HEADER.format(game=game):
        return set()
    return {parts[1] for parts in (line.split("\t") for line in lines[1:]) if parts[0] == "whole" and len(parts) == 2}


def known_names(folder: Path, game: int, slot: int, whole: set[str] | None = None) -> set[str]:
    """What split_name needs to read this village's names: the last names the player gave, and the
    names that are one first name (`whole`, else the record's)."""
    fixed = read_record(folder, game, slot)[1]
    whole = read_whole(folder, game, slot) if whole is None else whole
    return set(fixed.values()) | {WHOLE + name for name in whole}


def write_record(folder: Path, game: int, slot: int, rule: str, fixed: dict[tuple, str],
                 whole: set[str] | None = None) -> None:
    whole = read_whole(folder, game, slot) if whole is None else whole
    path = record_path(folder, game, slot)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [RECORD_HEADER.format(game=game), f"rule\t{rule}"]
    lines += [f"set\t{first}\t{head}\t{body}\t{last}" for (first, head, body), last in sorted(fixed.items())]
    lines += [f"whole\t{name}" for name in sorted(whole)]
    _write(path, ("\n".join(lines) + "\n").encode("utf-8"))


def everyone(folder: Path, game: int, slot: int) -> tuple[list[Living], dict[tuple, tuple]]:
    """Every villager the save and the logs know: the living (the save's) and the dead, disappeared
    and gone (the logs', `alive` False) -- the owner: "should retroactively give last names to people
    no longer in the village but still recorded in the logs" -- and each one's (father, mother)."""
    import vv_genealogy as gen
    people = living(folder, game, slot)
    village = gen.load_village(folder, game, slot, full_names=False)   # the names as the records carry them
    # Only what the logs say: an Arrived record whose "How:" is not "Founder".  A parentless villager
    # merely first seen later (an A New Home baby from before the parentage records) is not taken
    # for an arrival (review, 2026-10-07).
    # An event's villager with parents on its record (The Secret City's Crystal of Reflections copies
    # the original's parents) is an arrival too: a birth never has an Arrived record (Codex, #566).
    arrivals = {p.key for p in village.known()
                if not p.upcoming and p.arrived and p.how and p.how != "Founder"}
    for v in people:
        v.arrived = v.identity in arrivals
    have = {v.identity for v in people}
    for p in sorted(village.known(), key=lambda q: q.order_key()):
        if p.key not in have and not p.alive and p.head is not None and p.body is not None:
            people.append(Living(-1, p.name, p.sex or "", p.head, p.body, 0, "", alive=False,
                                 arrived=p.key in arrivals))
            have.add(p.key)
    parents = {p.key: tuple(village.people[q].key if q is not None else None for q in (p.father, p.mother))
               for p in village.known()}
    return people, parents


# ARRIVALS.  The owner, 2026-10-07: "All newly-spawned villagers from events will default to no
# last name (because otherwise everyone will have the wrong last name)".  A villager the logs say
# arrived -- an Arrived record whose "How:" is not "Founder" (an island event's newcomer, the
# Barrel O' Babies, a Custom Island Event's villager, a converted Heathen) -- has no last
# name by default: no family name of their own, under any rule.  The founders, the village's first
# villagers, keep one of their own (separate).  The player can still pick or type one, and an
# arrival whose name already carries a last name keeps it.


def separate(people: list[Living], parents: dict[tuple, tuple], pool: list[str],
             carried=own_last_name) -> dict[tuple, str]:
    """A last name of their own for each living villager with no recorded parent (the owner:
    "unrelated and single individuals have no family yet and should get separate last names"):
    their family's from the game's list `pool` when no other such villager has it, else the next
    one in the list nobody has (the list's names are reused only when every one is taken).  One
    whose name already carries a last name keeps it.  An arrival gets none (ARRIVALS)."""
    alone = [v for v in people if parents.get(v.identity, (None, None)) == (None, None)
             and not carried(v.name) and not v.arrived]
    taken = {carried(v.name) for v in people} - {""}
    out: dict[tuple, str] = {}
    for v in alone:                         # each their own family's first ...
        if v.default and v.default not in taken:
            out[v.identity] = v.default
            taken.add(v.default)
    for v in alone:                         # ... then one nobody has, for those whose was taken
        if v.identity not in out:
            name = next((n for n in pool if n not in taken), v.default)
            out[v.identity] = name
            taken.add(name)
    return out


def inherited(people: list[Living], parents: dict[tuple, tuple], rule: str,
              pool: list[str] | None = None, fixed: dict[tuple, str] | None = None,
              carried=own_last_name) -> dict[tuple, str]:
    """Each living villager's last name by `rule` ("" for none): the father's, the mother's,
    either parent's at random, or one at random from the game's list -- a parent's being the one
    their name carries, else (a living parent being given one now) the one this rule gives them,
    parents before children.  Without the parent the rule names, the other parent's; without
    either, their own (separate) or the family's -- or, for an arrival, none (ARRIVALS).  The
    random pick is the same each time for the same villager.  "each" leaves every one to the player: a villager keeps the last name they carry until the player gives another.  `parents` maps a villager (name, head, body) to (father, mother).  With
    the game's list of last names (`pool`), a villager with no recorded parent has one of their own
    (separate).  `fixed`: the last names the player gave villagers themselves ("" none) -- theirs,
    and their descendants inherit them by the rule (the owner, 2026-10-07: name Chapa "Chapa
    Chapstick", and with "From the mother" her descendants are Chapsticks).  `carried` reads the
    last name a name already has: a villager listed here with a recorded parent takes the rule's
    name, not the one carried (a change of rule re-derives the family); one without keeps theirs."""
    fixed = fixed or {}
    if rule in PLAYER_RULES:
        return {v.identity: fixed[v.identity] if v.identity in fixed else carried(v.name) for v in people}
    if rule == "list":
        return {v.identity: fixed[v.identity] if v.identity in fixed
                else carried(v.name) if v.arrived                   # ARRIVALS: none by default
                else random.Random(zlib.crc32(repr(v.identity).encode("utf-8"))).choice(pool) if pool
                else v.default for v in people}
    living_by = {v.identity: v for v in people}
    own = separate(people, parents, pool, carried) if pool else {}
    out: dict[tuple, str] = {}

    def last_of(key, seen: frozenset) -> str:
        if key is None:
            return ""
        if key not in living_by:
            return carried(key[0])
        return give(living_by[key], seen)

    def give(v: Living, seen: frozenset = frozenset()) -> str:
        if v.identity in out:
            return out[v.identity]
        if v.identity in fixed:                 # the player's own choice
            out[v.identity] = fixed[v.identity]
            return out[v.identity]
        if v.identity in seen:                  # a loop in the records: their own
            return own.get(v.identity) or v.default
        father, mother = parents.get(v.identity, (None, None))
        if father is None and mother is None and carried(v.name):   # no parent: the name they have
            out[v.identity] = carried(v.name)
            return out[v.identity]
        if v.arrived:                           # ARRIVALS: none by default, parents on record or not
            out[v.identity] = carried(v.name)
            return out[v.identity]
        seen = seen | {v.identity}
        dad, mum = last_of(father, seen), last_of(mother, seen)
        if rule == "father":
            result = dad or mum
        elif rule == "mother":
            result = mum or dad
        elif dad and mum and carried(v.name) in (dad, mum):
            # "random": a child carrying either parent's last name already had its 50:50 -- the
            # game's own at the birth (VVFP Last Names' VvfpRuleLastName, the owner, 2026-10-08).
            result = carried(v.name)
        else:                                   # "random": 50:50 for each child (the owner)
            pick = random.Random(zlib.crc32(repr(v.identity).encode("utf-8")))
            result = pick.choice([dad, mum]) if dad and mum else (dad or mum)
        result = result or own.get(v.identity) or v.default
        out[v.identity] = result
        return result

    for v in people:
        give(v)
    return out


def has_last_name(game: int, name: str) -> bool:
    checker = tools.load_checker()
    return name.rpartition(" ")[2] in checker.LAST_NAMES[game] and " " in name


def name_problem(game: int, name: str, last: str) -> str | None:
    """Why `name` + " " + `last` cannot be given, or None."""
    if not last:
        return "No last name."
    if any(not (0x20 < ord(ch) < 0x7F) for ch in last):
        return "A last name is one word of printable letters, no spaces or accents."
    if len(name) + 1 + len(last) > ROOM[game]:
        return f"{name} {last} is longer than the game's {ROOM[game]} characters."
    return None


# ---------------------------------------------------------------------------
# The plan: every file's new bytes
# ---------------------------------------------------------------------------

@dataclass
class Change:
    path: Path
    original: bytes
    updated: bytes
    what: str


@dataclass
class Question:
    key: str
    text: str
    options: dict[str, str]                         # answer -> new name ("" for none)
    default: str
    who: tuple = ()                                 # the (name, head, body) the records carry


@dataclass
class Plan:
    renames: dict[tuple, str]                       # (name, head, body) -> new name
    changes: list[Change] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    questions: list[Question] = field(default_factory=list)


NOT_THEM = "No: someone else (leave the name)"


def _put_name(buf: bytearray, at: int, cap: int, name: str) -> None:
    encoded = name.encode("latin-1")
    if len(encoded) + 1 > cap:
        raise LastNamesError(f"{name!r} does not fit a {cap}-byte name field.")
    buf[at:at + cap] = encoded + b"\0" * (cap - len(encoded))


def _title_identity(data, at: int, f: Fields) -> int:
    """native/shared/custom_titles.h vv_title_identity: name, 0xFF, likes, dislikes."""
    h = _fnv(FNV_BASIS, bytes(data[at:at + f.name_cap]).split(b"\0", 1)[0])
    h = _fnv(h, b"\xff")
    h = _fnv(h, bytes(data[at + f.likes:at + f.likes + 4 * f.slots]))
    h = _fnv(h, bytes(data[at + f.dislikes:at + f.dislikes + 4 * f.slots]))
    return h or 1


def _mask_identities(game: int, data, at: int) -> tuple[int, int, int]:
    """(identity, The Tree of Life's version-2 identity, name hash), as the checker reads them."""
    checker = tools.load_checker()
    if game == 1:
        raw = bytes(data[at - 0x34:at - 0x34 + checker.VV1_STRIDE])
        h = checker._fnv_text(FNV_BASIS, raw[0x34:0x34 + 0x1C])
        h = checker._fnv(h, b"\xff" + raw[0x350 - 0x33C:0x354 - 0x33C] + raw[0x36C - 0x33C:0x370 - 0x33C])
        return (h or 1), 0, 0
    return checker.mask_identity(game, bytes(data), at, checker.LAYOUTS[game])


def plan(folder: Path, game: int, slot: int, chosen: dict[tuple, str],
         answers: dict[str, str] | None = None, whole: set[str] | None = None) -> Plan:
    """What giving `chosen` ((name, head, body) -> last name) changes, file by file.  Reads only.

    Records whose name a renamed villager has but whose looks are no living villager's -- the
    same villager before Change Appearance, or another of the same name -- are asked about
    (Plan.questions); `answers` renames those the player says are them."""
    renames: dict[tuple, str] = {}
    known = known_names(folder, game, slot, whole)
    people, _parents = everyone(folder, game, slot)
    for v in people:
        if v.identity not in chosen:
            continue
        last = chosen[v.identity]
        if last == split_name(game, v.name, known)[1]:
            continue
        new = with_last(game, v.name, last, known)
        problem = name_problem(game, "", last) if last else None   # one printable word
        if problem:
            raise LastNamesError(f"{v.name}: {problem}")
        if len(new) > ROOM[game]:
            raise LastNamesError(f"{new} is longer than the game's {ROOM[game]} characters.")
        renames[v.identity] = new
    return plan_renames(folder, game, slot, renames, answers, dead=True, ask=True)


def plan_renames(folder: Path, game: int, slot: int, renames: dict[tuple, str],
                 answers: dict[str, str] | None = None, dead: bool = False, ask: bool | None = None) -> Plan:
    """What renaming each (name, head, body) to its new whole name changes, file by file.  Reads only.

    With `dead` (Number Duplicate Names), villagers no longer living are renamed too -- in their
    records and as the parents the save and the logs name -- and nobody is asked about look-alikes:
    each numbered villager is one name, head and body.  `ask` (default: not `dead`) asks about
    records with a renamed name but other looks; Last Names renames the dead and still asks."""
    folder = Path(folder)
    # Every rename is held here too, whoever asks for it (the owner: a character limit "IN EVERY
    # SINGLE PLACE A RENAME (OUTSIDE OF THE GAME) CAN HAPPEN"): the game's room, printable text only.
    for new in renames.values():
        if not new or len(new) > ROOM[game] or not storable(new):
            raise LastNamesError(f"{new!r} cannot be a name: the game takes 1 to {ROOM[game]} printable "
                                 "characters.")
    f = FIELDS[game]
    people = living(folder, game, slot, bodies=dead)
    result = Plan(renames)
    if not renames:
        return result
    # A renamed villager's earlier looks -- before Change Appearance, linked by the "Appearance
    # changed" records -- are the same villager: their records and the parent names saved with them
    # follow, so the link still holds under the new name (self-review, #558).
    import vv_genealogy as gen
    looks = gen._Registry()
    gen._appearance_changes(looks, folder, game, slot)
    renames = dict(renames)
    for old in looks.relooked:
        now = looks.current(old)
        if now in renames and old not in renames:
            renames[old] = renames[now]
    # What a name with no looks beside it becomes: every holder of the name, each as it will be
    # called (one not renamed keeps the name).  A name-only rewrite happens only when that is one
    # new name (Codex, #553): an unrenamed namesake makes the name ambiguous.
    by_name: dict[str, set] = {}
    for v in people:
        by_name.setdefault(v.name, set()).add(renames.get(v.identity, v.name))
    for (name, _head, _body), new in renames.items():
        by_name.setdefault(name, set()).add(new)
    by_name = {old: news for old, news in by_name.items() if len(news) == 1 and old not in news}

    # The save.
    path = save_path(folder, game, slot)
    original = path.read_bytes()
    after = bytearray(original)
    # A parent reference written before that parent's change of looks is asked about with the
    # logs' records (Codex, #553); a "yes" renames it in the save, the rosters and the logs.
    references = []
    if f.father is not None:
        fh, fb, mh, mb, eh, eb = f.looks
        for v in people:
            for off, cap, head, body in ((f.father, f.parent_cap, fh, fb), (f.mother, f.parent_cap, mh, mb),
                                         (f.expecting, 0x18, eh, eb)):
                references.append((_cstr(original, v.at + off, cap), _i32(original, v.at + head),
                                   _i32(original, v.at + body)))
    if (not dead) if ask is None else ask:
        result.questions = _look_alike_questions(folder, game, slot, people, renames, references)
    asked = dict(renames)
    for q in result.questions:
        new = q.options.get((answers or {}).get(q.key, ""), "")
        if new:
            asked[q.who] = new
    title_map: dict[int, int] = {}
    mask_map: dict[int, int] = {}
    before_ids = {v.at: (_title_identity(original, v.at, f), _mask_identities(game, original, v.at)) for v in people}
    for v in people:
        new = renames.get(v.identity)
        if new:
            _put_name(after, v.at, f.name_cap, new)
    if f.father is not None:
        # A parent is the renamed villager only by name AND looks: a dead namesake is not.
        fh, fb, mh, mb, eh, eb = f.looks
        for v in people:
            for off, cap, head, body in ((f.father, f.parent_cap, fh, fb), (f.mother, f.parent_cap, mh, mb),
                                         (f.expecting, 0x18, eh, eb)):
                parent = (_cstr(original, v.at + off, cap), _i32(original, v.at + head),
                          _i32(original, v.at + body))
                if parent in asked:
                    _put_name(after, v.at + off, cap, asked[parent])
    # A title or mask is kept by an identity two villagers may share (the same name and likes, or
    # name and parents).  Given different names, the game could no longer tell which of them a
    # title or mask was for: when such an identity is in use in a titles or mask file, that is
    # refused rather than guessed (Codex, #553).  An identity no file holds decides nothing.
    owner: dict[int, tuple[int, str]] = {}
    conflicts: dict[int, str] = {}
    for v in people:
        old_title, old_masks = before_ids[v.at]
        new_title, new_masks = _title_identity(after, v.at, f), _mask_identities(game, after, v.at)
        for old_id, new_id in ((old_title, new_title), *zip(old_masks, new_masks)):
            if not old_id or not new_id:
                continue
            seen = owner.setdefault(old_id, (new_id, v.name))
            if seen[0] != new_id:
                conflicts[old_id] = f"{seen[1]} and {v.name}"
        if new_title != old_title:
            title_map[old_title] = new_title
        for old_id, new_id in zip(old_masks, new_masks):
            if old_id and new_id and old_id != new_id:
                mask_map[old_id] = new_id
    # The graves of the dead renamed (Number Duplicate Names, last names for the gone).
    graves = _rename_graves(after, game, renames, _death_ages(folder, game, slot), result) if dead else []
    result.changes.append(Change(path, original, bytes(after), "the save"))
    _plan_grave_files(result, folder, game, slot, graves)

    data_dir = folder / tools.DATA
    _plan_masks(result, game, slot, data_dir, mask_map, conflicts)
    _plan_u32_file(result, data_dir / "Custom Titles" / f"Custom Titles - Save {slot}.dat",
                   b"VCT1", 2, game, 16, 40, 4, title_map, "custom titles", conflicts)
    if game == 5:
        _plan_u32_file(result, data_dir / "Former Heathens" / f"Former Heathens - Save {slot}.dat",
                       b"VFH1", 1, game, 16, 8, 0, title_map, "former Heathens", conflicts)
    if game == 1:
        _plan_vv1_parentage(result, folder, data_dir, slot, people, renames, asked, by_name)
    _plan_unaccounted(result, game, slot, data_dir, renames, asked)
    renamed = {name for name, _head, _body in renames}
    _plan_statistics(result, game, slot, data_dir, by_name, renamed)
    _plan_logs(result, folder, game, slot, asked, by_name, dead, renamed)
    _plan_family_trees(result, folder, game, slot, asked)
    return result


def _look_alike_questions(folder: Path, game: int, slot: int, people: list[Living],
                          renames: dict[tuple, str], references: list[tuple] = ()) -> list[Question]:
    """One question per (name, head, body) the logs or the save's parent `references` name that
    is a renamed villager's old name but no living villager's looks, and no dead villager's
    record: is it them?"""
    import vv_log_additions as additions
    checker = tools.load_checker()
    living_ids = {v.identity for v in people}
    renamed_by_name: dict[str, list[tuple[Living, str]]] = {}
    for v in people:
        if v.identity in renames:
            renamed_by_name.setdefault(v.name, []).append((v, renames[v.identity]))
    dead: set[tuple] = set()
    seen: dict[tuple, int] = {}
    for who in references:
        if who[0] in renamed_by_name and who not in living_ids:
            seen[who] = seen.get(who, 0) + 1
    villages = additions.current_villages(folder, game, slot)
    for path in checker.log_files(folder):
        lines = additions.read_lines(path)
        for b in additions.blocks(path, lines):
            if not b.of(slot, game, villages):
                continue
            if b.heading.startswith(("Death", "Disappeared", "Epitaph")):
                dead.add(b.identity)
                continue
            for k, line in enumerate(b.lines):
                m = PERSON_LINE.match(line)
                if not m:
                    continue
                who = additions._who_at(lines, b.start + k)
                if who[0] in renamed_by_name and who not in living_ids and who[1] is not None:
                    seen[who] = seen.get(who, 0) + 1
    out = []
    for who, count in sorted(seen.items(), key=lambda kv: (kv[0][0], kv[0][1] or 0, kv[0][2] or 0)):
        if who in dead:
            continue
        options = {f"Yes: {v.name} (now head {v.head}, body {v.body}) -> {new}": new
                   for v, new in renamed_by_name[who[0]]}
        options[NOT_THEM] = ""
        out.append(Question(
            f"who|{who[0]}|{who[1]}|{who[2]}",
            f"{count} record(s) name {who[0]} with head {who[1]} and body {who[2]}, looks no living villager "
            f"has now. Are they the villager you are renaming (before a change of looks)?",
            options, NOT_THEM, who))
    return out


def _replace_u32s(buf: bytearray, at: int, count: int, step: int, mapping: dict[int, int],
                  conflicts: dict[int, str] | None = None) -> int:
    n = 0
    for i in range(count):
        p = at + i * step
        value = struct.unpack_from("<I", buf, p)[0]
        if conflicts and value in conflicts:
            raise LastNamesError(
                f"{conflicts[value]} look the same to the game's custom titles and masks; "
                "give them the same last name (or none to both).")
        if value in mapping:
            struct.pack_into("<I", buf, p, mapping[value])
            n += 1
    return n


def _plan_masks(result: Plan, game: int, slot: int, data_dir: Path, mask_map: dict[int, int],
                conflicts: dict[int, str]) -> None:
    checker = tools.load_checker()
    name = checker.VV_MASK_FILES.get(game, "Village Masks - Save {slot}.dat").format(slot=slot)
    for path in (data_dir / "Village Masks" / name, data_dir / name):
        if not path.is_file():
            continue
        original = path.read_bytes()
        buf = bytearray(original)
        magic = bytes(buf[:4])
        n = 0
        # Each format as its companion reads it (scripts/vvfp_consistency_check.py read_mask_file);
        # a file too short for its own format is left as it is (Codex, #553).
        if game == 1 and magic == b"VM02" and len(buf) >= 132 + 1024:
            n = _replace_u32s(buf, 132, 256, 4, mask_map, conflicts)
        elif game == 2 and magic in (b"VM04", b"VM06") and len(buf) >= 4 + 1024 + 256:
            n = _replace_u32s(buf, 4, 256, 4, mask_map, conflicts)
        elif game == 3 and magic == b"MSK4" and len(buf) >= 260 + 1024:
            n = _replace_u32s(buf, 260, 256, 4, mask_map, conflicts)
        elif game == 4 and magic == b"VVMK" and len(buf) >= 12:
            version, count = struct.unpack_from("<II", buf, 4)
            if version in (2, 3) and count in (150, 256) and len(buf) >= 12 + count * (9 if version == 3 else 5):
                n = _replace_u32s(buf, 12 + count, count, 4, mask_map, conflicts)
                if version == 3:
                    n += _replace_u32s(buf, 12 + count * 5, count, 4, mask_map, conflicts)
            else:
                result.notes.append(f"{path.name} is not a mask file this game reads; left as it is.")
        elif game == 5 and magic in (b"VM05", b"VM06", b"VM25", b"VM26"):
            count = 150 if magic in (b"VM05", b"VM06") else 256
            if len(buf) >= 4 + count * 4 + count // 2:
                n = _replace_u32s(buf, 4, count, 4, mask_map, conflicts)
        if n:
            result.changes.append(Change(path, original, bytes(buf), "the masks"))


def _plan_u32_file(result: Plan, path: Path, magic: bytes, version: int, game: int, header: int,
                   entry: int, field_at: int, mapping: dict[int, int], what: str,
                   conflicts: dict[int, str]) -> None:
    """A file of `count` fixed entries whose u32 at `field_at` is an identity.  A file that is not
    exactly its own format of this game (magic, version, the game at offset 8, header + count *
    entry bytes) is left as it is: games sharing a folder share these files' names (Codex, #553)."""
    if not path.is_file():
        return
    original = path.read_bytes()
    if (len(original) < header or original[:4] != magic or struct.unpack_from("<I", original, 4)[0] != version
            or struct.unpack_from("<I", original, 8)[0] != game):
        result.notes.append(f"{path.name} is not a {what} file this patcher writes; left as it is.")
        return
    count = struct.unpack_from("<I", original, 12)[0]
    if len(original) != header + count * entry:
        result.notes.append(f"{path.name} is damaged (its length does not match its count); left as it is.")
        return
    buf = bytearray(original)
    if _replace_u32s(buf, header + field_at, count, entry, mapping, conflicts):
        result.changes.append(Change(path, original, bytes(buf), what))


def _dead_names(folder: Path, game: int, slot: int) -> set[str]:
    """Every name a Death or Disappeared record of this slot's village carries."""
    import vv_log_additions as additions
    out = set()
    for b in additions.person_blocks(folder, slot, game):
        if b.heading.startswith(("Death", "Disappeared")) and b.value("Name"):
            out.add(b.value("Name"))
    return out


def _plan_vv1_parentage(result: Plan, folder: Path, data_dir: Path, slot: int, people: list[Living],
                        renames: dict[tuple, str], asked: dict[tuple, str], by_name: dict[str, set]) -> None:
    """A New Home's Parentage Records: the roster is matched as the companion matches it -- by
    name and looks when the file recorded them, else by gender, family and name when every living
    holder of those takes one new name (Codex, #553); a father / mother / expected-father name by
    its looks (`asked`: a "yes" to a look-alike question too), or, in an entry written before looks
    were kept, by a name every living holder and no dead villager shares."""
    by_scalar: dict[tuple, set] = {}
    for v in people:
        by_scalar.setdefault((v.name, 1 if v.sex == "Male" else 2, v.family), set()).add(
            renames.get(v.identity, v.name))
    dead = _dead_names(folder, 1, slot)
    for path in (layout.find(data_dir.parent, f"{layout.DATA}\\{layout.PARENTS_VV1}\\"
                                              f"Virtual Villagers 1 Parentage Records - Save {slot}.dat"),
                 data_dir / f"Virtual Villagers 1 Parentage Records - Save {slot}.dat"):
        if not path.is_file():
            continue
        original = path.read_bytes()
        if original[:4] != b"VP02" or len(original) < 12 + 256 * 36 + 256 * 92:
            continue
        buf = bytearray(original)
        n = 0
        for i in range(256):
            occ = 12 + i * 36
            if buf[occ] not in (1, 2):
                continue
            name = _cstr(buf, occ + 8, 28)
            new = None
            if buf[occ + 2] and buf[occ + 3]:
                new = renames.get((name, buf[occ + 2] - 1, buf[occ + 3] - 1))
            else:
                news = by_scalar.get((name, buf[occ], _i32(buf, occ + 4)), set())
                new = next(iter(news)) if len(news) == 1 and name not in news else None
            if new:
                _put_name(buf, occ + 8, 28, new)
                n += 1
        for i in range(256):
            e = 12 + 256 * 36 + i * 92
            for looks, at in ((0, 8), (2, 36), (4, 64)):
                name = _cstr(buf, e + at, 28)
                if not name:
                    continue
                if buf[e + looks] and buf[e + looks + 1]:
                    new = asked.get((name, buf[e + looks] - 1, buf[e + looks + 1] - 1))
                else:
                    news = by_name.get(name, set())
                    new = next(iter(news)) if len(news) == 1 and name not in dead else None
                if new:
                    _put_name(buf, e + at, 28, new)
                    n += 1
        if n:
            result.changes.append(Change(path, original, bytes(buf), "A New Home's parents"))


def _plan_unaccounted(result: Plan, game: int, slot: int, data_dir: Path, renames: dict[tuple, str],
                      asked: dict[tuple, str]) -> None:
    name = f"Virtual Villagers {game} Villagers at Last Save - Save {slot}.dat"
    rec = RECORD[game]
    for path in (layout.find(data_dir.parent, f"{layout.DATA}\\Unaccounted Villagers\\{name}"),
                 data_dir / f"Virtual Villagers {game} Village Roster - Save {slot}.dat"):
        if not path.is_file():
            continue
        original = path.read_bytes()
        if original[:4] != b"VCR1" or len(original) < 32:
            continue
        count, lo, hi = struct.unpack_from("<III", original, 12)
        rec_name = RECORD[game]["name"]
        if not lo <= rec_name < hi or len(original) != 32 + count * (16 + hi - lo):
            result.notes.append(f"{path.name} is damaged or another build's; left as it is.")
            continue
        size = 16 + (hi - lo)
        buf = bytearray(original)
        n = 0
        for i in range(count):
            base = 32 + i * size + 16 - lo
            if base + hi > len(buf):
                break
            cap = FIELDS[game].name_cap
            own = (_cstr(buf, base + rec["name"], cap), _i32(buf, base + rec["head"]), _i32(buf, base + rec["body"]))
            if own in renames:
                _put_name(buf, base + rec["name"], cap, renames[own])
                n += 1
            for key in ("father", "mother", "expecting"):
                if key in rec:
                    at, head, body = rec[key]
                    width = 0x18 if key == "expecting" else FIELDS[game].parent_cap
                    parent = (_cstr(original, base + at, width), _i32(original, base + head),
                              _i32(original, base + body))
                    if parent in asked:
                        _put_name(buf, base + at, width, asked[parent])
                        n += 1
        if n:
            result.changes.append(Change(path, original, bytes(buf), "the Unaccounted roster"))


def _plan_family_trees(result: Plan, folder: Path, game: int, slot: int, renames: dict[tuple, str]) -> None:
    """The Family Tree Maker's edits for this save -- its edits file and the save's .vvtree files --
    keyed by each villager's name, re-keyed so the marks, text, sizes and places follow them
    (Codex, #555)."""
    import json
    import vv_family_tree as ft
    import vv_tribe_rename
    paths = [ft.Edits.path(folder, game, slot)]
    try:                                        # a reused slot's old tribe keeps its own tree (Codex, #557)
        tribe = vv_tribe_rename.save_name({g.number: g for g in vv_tribe_rename.GAMES}[game],
                                          save_path(folder, game, slot).read_bytes())
    except (OSError, KeyError, ValueError):
        tribe = None
    trees = Path(folder) / ft.TREES
    if trees.is_dir():
        for path in sorted(trees.glob(f"*{ft.TREE_SUFFIX}")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(data, dict) and (data.get("game"), data.get("slot")) == (game, slot) \
                    and tribe and data.get("tribe") == tribe:
                paths.append(path)
    for path in paths:
        if not path.is_file():
            continue
        original = path.read_bytes()
        updated = ft.renamed_keys(original.decode("utf-8"), renames).encode("utf-8")
        if updated != original:
            result.changes.append(Change(path, original, updated, "the family tree's edits"))


def _first_line(path: Path) -> str:
    try:
        return path.read_bytes().decode("latin-1").split("\n", 1)[0].rstrip("\r")
    except OSError:
        return ""


def _left(result: Plan, path: Path, names: set[str]) -> None:
    """A note: lines of `path` naming a renamed villager without saying which one keep the name."""
    if names:
        result.notes.append(f"{path.name} names {', '.join(sorted(names))} without saying which villager, so "
                            "those lines keep the name.")


def _plan_statistics(result: Plan, game: int, slot: int, data_dir: Path, by_name: dict[str, set],
                     renamed: set[str] = frozenset()) -> None:
    """The Village Statistics roster and Village Elders.  Games sharing a folder share these
    files' names (Codex, #553): the Elders file names its game on its first line, and the roster
    (which does not) is this game's only when the slot's "Village Statistics - Save N.dat" says so.
    A name these files hold for more than one new name stays, and is reported (Codex, #557)."""
    unique = {old: next(iter(news)) for old, news in by_name.items() if len(news) == 1}
    folder = data_dir / "Village Statistics"
    roster = layout.find(data_dir.parent, f"{layout.DATA}\\Village Statistics\\Villagers Counted - Save {slot}.dat")
    statistics = _first_line(folder / f"Village Statistics - Save {slot}.dat")
    if roster.is_file() and statistics != f"VVFP VILLAGE STATISTICS v1 game={game}":
        result.notes.append(f"{roster.name} may be another game's (its Village Statistics file does not "
                            "name this game); left as it is.")
    elif roster.is_file():
        original = roster.read_bytes()
        lines = original.decode("latin-1").split("\n")
        changed = False
        left = set()
        for k, line in enumerate(lines):
            parts = line.split("\t")
            if len(parts) == 3 and parts[1] in unique:
                parts[1] = unique[parts[1]][:31]
                lines[k] = "\t".join(parts)
                changed = True
            elif len(parts) == 3 and parts[1] in renamed:
                left.add(parts[1])
        _left(result, roster, left)
        if changed:
            result.changes.append(Change(roster, original, "\n".join(lines).encode("latin-1"),
                                        "the statistics roster"))
    elders = data_dir / "Village Elders" / f"Village Elders - Save {slot}.dat"
    if elders.is_file() and _first_line(elders) != f"VVFP VILLAGE ELDERS v2 game={game}":
        result.notes.append(f"{elders.name} is not this game's version 2 Village Elders file; left as it is.")
    elif elders.is_file():
        original = elders.read_bytes()
        lines = original.decode("latin-1").split("\n")
        changed = False
        left = set()
        for k, line in enumerate(lines):
            parts = line.split("\t")
            if parts and parts[0] == "E" and len(parts) >= 5:
                for col in (2, 3, 4):
                    if parts[col].rstrip("\r") in unique:
                        tail = "\r" if parts[col].endswith("\r") else ""
                        parts[col] = unique[parts[col].rstrip("\r")][:39] + tail
                        changed = True
                    elif parts[col].rstrip("\r") in renamed:
                        left.add(parts[col].rstrip("\r"))
                lines[k] = "\t".join(parts)
        _left(result, elders, left)
        if changed:
            result.changes.append(Change(elders, original, "\n".join(lines).encode("latin-1"), "the Village Elders"))


# ---------------------------------------------------------------------------
# The logs
# ---------------------------------------------------------------------------

PERSON_LINE = re.compile(r"^(\s+)(Name|Child|Mother|Father): (.*)$")


def _plan_logs(result: Plan, folder: Path, game: int, slot: int, renames: dict[tuple, str],
               by_name: dict[str, set], dead: bool = False, renamed: set[str] = frozenset()) -> None:
    """Every record of a renamed villager: a "Name:" / "Child:" / "Mother:" / "Father:" line whose
    name, head and body are theirs.  A Death, Disappeared or Epitaph record is never theirs when
    only the living are renamed.  A line without looks is renamed when the name alone is unique
    among those renamed; one naming a renamed villager without saying which stays, and is reported."""
    import vv_log_additions as additions
    checker = tools.load_checker()
    villages = additions.current_villages(folder, game, slot)
    for path in checker.log_files(folder):
        original = path.read_bytes()
        crlf = b"\r\n" in original
        lines = original.decode("latin-1").replace("\r\n", "\n").split("\n")
        n = 0
        left = set()
        for b in additions.blocks(path, lines):
            if not b.of(slot, game, villages) or not dead and b.heading.startswith(
                    ("Death", "Disappeared", "Epitaph")):
                continue
            for k, line in enumerate(b.lines):
                m = PERSON_LINE.match(line)
                if not m:
                    continue
                name = m.group(3).strip()
                who = additions._who_at(lines, b.start + k)
                if b.heading == "Appearance changed":   # the villager by the look they changed from
                    head, body = b.value("Old head"), b.value("Old body")
                    if head and body and head.lstrip("-").isdigit() and body.lstrip("-").isdigit():
                        who = (name, int(head), int(body))
                new = renames.get((name, who[1], who[2]))
                if new is None and who[1] is None and len(by_name.get(name, set())) == 1:
                    new = next(iter(by_name[name]))
                if new:
                    lines[b.start + k] = f"{m.group(1)}{m.group(2)}: {new}"
                    n += 1
                elif who[1] is None and name in renamed:
                    left.add(name)
        _left(result, path, left)
        if n:
            text = "\n".join(lines)
            if crlf:
                text = text.replace("\n", "\r\n")
            result.changes.append(Change(path, original, text.encode("latin-1"), "the logs"))
    _plan_repairs_logs(result, folder, game, slot, by_name, villages, renames)


def _plan_repairs_logs(result: Plan, folder: Path, game: int, slot: int, by_name: dict[str, set],
                       villages, renames: dict[tuple, str] | None = None) -> None:
    """The Repairs log (which the checker's log list leaves out) names villagers in its own words --
    "Pregnancy: Chapa Wanjiko -- father Usutu Bahati" -- with no looks, so a name there is renamed
    only when it is one villager's alone (`by_name`), as a whole name: "Kaula Bahati" never touches
    "Kaula Bahati I" (the owner: renames are retroactive in every log, and the logs match the save)."""
    import vv_log_additions as additions
    checker = tools.load_checker()
    unique = {old: next(iter(news)) for old, news in by_name.items() if len(news) == 1 and old.strip()}
    if renames is not None and unique:
        # Unique among every villager the logs know, not just the living: a buried namesake who keeps
        # their name keeps every line too (Codex, #566).
        logged: dict[str, set] = {}
        lookless: set[str] = set()
        for b in additions.person_blocks(Path(folder), slot, game):
            name, head, body = b.identity
            if name not in unique:
                continue
            if head is not None and body is not None:
                logged.setdefault(name, set()).add((name, head, body))
            elif b.heading.startswith(("Death", "Disappeared", "Left", "Unaccounted")):
                # A gone villager's older record without looks may be a namesake's: not unique
                # (Codex, #566).
                lookless.add(name)
        renamed = set(renames)
        unique = {old: new for old, new in unique.items()
                  if old not in lookless and logged.get(old, set()) <= renamed}
    if not unique:
        return
    # A whole name only: after the start of the line or a space, and followed by what ends a name in
    # the log's sentences (" --", " (", ",", ")", ";", A New Home's "... expected father <name> cleared"
    # or the end of the line) -- so renaming "Kaula"
    # never touches "Kaula Bahati" (review, 2026-10-07).
    pattern = re.compile(r"(?:^|(?<=[\s:]))(" + "|".join(re.escape(n) for n in sorted(unique, key=len, reverse=True))
                         + r")(?=\s--|\s\(|[,);]|\scleared\b|\s*$)")
    for top in checker.LOG_FOLDERS:
        root = Path(folder) / top
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.txt")):
            if path.parent.name not in ("Repairs", layout.REPAIRS_LOGS):
                continue
            original = path.read_bytes()
            crlf = b"\r\n" in original
            lines = original.decode("latin-1").replace("\r\n", "\n").split("\n")
            n = 0
            for b in additions.blocks(path, lines):
                if not b.of(slot, game, villages):
                    continue
                for k in range(len(b.lines)):
                    line = lines[b.start + k]
                    new_line, count = pattern.subn(lambda m: unique[m.group(1)], line)
                    if count:
                        lines[b.start + k] = new_line
                        n += count
            if n:
                text = "\n".join(lines)
                if crlf:
                    text = text.replace("\n", "\r\n")
                result.changes.append(Change(path, original, text.encode("latin-1"), "the Repairs log"))


# ---------------------------------------------------------------------------
# Applying
# ---------------------------------------------------------------------------

@dataclass
class Result:
    renamed: dict[tuple, str]
    files: list[Path]
    backup: vv_save_backup.BackupResult


def _write(path: Path, data: bytes) -> None:
    temporary = path.with_name(path.name + ".lastnames-tmp")
    try:
        with temporary.open("xb") as handle:
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
        raise LastNamesError(f"{path.name} did not read back as written.")


def give_last_names(folder: Path, game: int, slot: int, chosen: dict[tuple, str],
                    processes: vv_save_backup.ProcessController | None = None,
                    now: datetime | None = None, answers: dict[str, str] | None = None,
                    rule: str | None = None, mine: dict[tuple, str] | None = None,
                    whole: set[str] | None = None) -> Result:
    """Rename the chosen living villagers everywhere.  Refused (nothing changed) while the game
    runs; the save folder is backed up first; any failure puts every changed file back."""
    folder = Path(folder)
    controller = processes if processes is not None else vv_save_backup.WindowsProcesses()
    tools._refuse_if_running(folder, controller)
    try:
        work = plan(folder, game, slot, chosen, answers, whole)
    except (struct.error, ValueError, OSError) as exc:
        raise LastNamesError(f"A file could not be read ({exc}); nothing was changed.") from exc
    if not work.renames:
        raise LastNamesError("No villager was given a last name.")
    result = apply(folder, work, controller, now, BACKUP_LABEL, "giving the last names")
    if rule:                                    # what "right" is, for Check Saves & Logs' wrong last names
        _old_rule, fixed = read_record(folder, game, slot)
        known = known_names(folder, game, slot, whole) | {last for last in (mine or {}).values() if last}
        for (name, head, body), last in (mine or {}).items():
            fixed[(split_name(game, name, known)[0], head, body)] = last
        write_record(folder, game, slot, rule, fixed, whole)
    return result


def unrelated_namesakes(people: list[Living], parents: dict[tuple, tuple],
                        lasts: dict[tuple, str]) -> dict[tuple, tuple[str, list[str]]]:
    """Villagers who share a last name with a family they are not related to (the owner, 2026-10-07:
    "an alert ... if a villager who isn't related is sharing a last name with someone" -- Thabo
    Bahati, a new arrival, beside the established Bahati family).  Related means one family tree:
    joined by any parent and child the records know, so in-laws with a child together count as
    family (review, 2026-10-07); `lasts` is each villager's last name now ("" none).  For each last
    name held by more than one unrelated group, every villager outside its largest group is returned
    with (the last name, the names of the largest group's first few)."""
    root: dict = {}

    def find(k):
        root.setdefault(k, k)
        while root[k] != k:
            root[k] = root[root[k]]
            k = root[k]
        return k

    for child, pair in parents.items():
        for parent in pair:
            if parent is not None:
                root[find(parent)] = find(child)
    names = {v.identity: v.name for v in people}
    groups: dict[tuple, dict] = {}                  # last name -> family root -> villagers
    for v in people:
        if lasts.get(v.identity):
            groups.setdefault(lasts[v.identity], {}).setdefault(find(v.identity), []).append(v.identity)
    out: dict[tuple, tuple[str, list[str]]] = {}
    for last, families in groups.items():
        if len(families) < 2:
            continue
        ranked = sorted(families.values(), key=lambda members: -len(members))
        main = [names[k] for k in ranked[0]][:4]
        for members in ranked[1:]:
            for key in members:
                out[key] = (last, main)
    return out


def with_siblings(fixed: dict[tuple, str], parents: dict[tuple, tuple]) -> dict[tuple, str]:
    """The names the player set, given to each one's brothers and sisters (the same father and mother)
    the player has not set themselves -- a family is a couple and their children, one last name (the
    owner, 2026-10-07: "if one villager's last name is filled, the other members of their family
    should auto-adjust to that last name too based on the rules")."""
    out = dict(fixed)
    for key, last in fixed.items():
        couple = parents.get(key, (None, None))
        if couple == (None, None):
            continue
        for other, theirs in parents.items():
            if theirs == couple and other not in fixed:
                out.setdefault(other, last)
    return out


def wrong_last_names(folder: Path, game: int, slot: int) -> tuple[str, list[tuple[Living, str, str]]]:
    """(rule, [(villager, last name now, the one the rule gives)]): every villager -- living or
    gone -- whose last name is not the one the village's rule gives them from their parents (the
    owner: a check for "Wrong last names").  The record's rule, else "From the mother" (as the Last
    Names patch gives babies their mother's); without a record only names that carry a last name
    are checked.  A name the player gave is always right."""
    rule, fixed = read_record(folder, game, slot)
    known = known_names(folder, game, slot)
    people, parents = everyone(folder, game, slot)
    mine = {v.identity: fixed[key] for v in people
            if (key := (split_name(game, v.name, known)[0], v.head, v.body)) in fixed}
    carried = lambda name: split_name(game, name, known)[1]  # noqa: E731
    given = inherited(people, parents, rule or "mother", list(tools.load_checker().LAST_NAMES[game]),
                      with_siblings(mine, parents), carried)
    out = []
    for v in people:
        now = carried(v.name)
        should = given.get(v.identity, "")
        if v.identity in mine or now == should or (rule is None and not now) or rule in ("list", *PLAYER_RULES):
            continue
        out.append((v, now, should))
    return rule or "mother", out


def apply(folder: Path, work: Plan, controller: vv_save_backup.ProcessController, now: datetime | None,
          label: str, doing: str) -> Result:
    """Write a plan's changes: the save folder backed up first (`label` names the backup), refused
    while the game runs, every file swapped in and read back, every one put back on a failure."""
    try:
        backup = vv_save_backup.copy_save_folder(folder, now or datetime.now(), suffix=label)
    except vv_save_backup.BackupError as exc:
        raise LastNamesError(f"The backup failed, so nothing was changed. {exc}") from exc
    tools._refuse_if_running(folder, controller)
    done: list[Change] = []
    try:
        for change in work.changes:
            if change.path.read_bytes() != change.original:
                raise LastNamesError(f"{change.path.name} changed while {doing}.")
            done.append(change)
            _write(change.path, change.updated)
    except (OSError, LastNamesError) as exc:
        problems = []
        for change in reversed(done):
            try:
                if change.path.read_bytes() != change.original:
                    _write(change.path, change.original)
            except (OSError, LastNamesError) as undo:
                problems.append(f"{change.path.name}: {undo}")
        if problems:
            raise LastNamesError(f"{doing.capitalize()} failed ({exc}) and these files could not be put "
                                 f"back: {'; '.join(problems)}. Your backup is in {backup.backup_folder}.") from exc
        raise LastNamesError(f"{doing.capitalize()} failed ({exc}); every file was put back as it was. "
                             f"A backup is in {backup.backup_folder}.") from exc
    return Result(work.renames, [c.path for c in work.changes], backup)
