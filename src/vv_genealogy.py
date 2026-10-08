"""The Family Tree Maker and the Village Matchmaker: who descends from whom, each villager's generation, how closely any two
villagers are related, and which pairs the player's rules allow (all five games).

The owner (2026-10-07): "A log that tells you exactly who's descended from whom, what generation
they're in.  Helps you pair up villagers according to the rules the player sets and generates a
family tree for the current save file", the tree drawn with each villager's head, name and age in
game units and years, one colour per family line, twins and triplets joined by a triangle.  Every
rule is an optional toggle ("It's a small island unfortunately").

Where the family comes from -- read only, nothing is written but the helper's own report:

* the save: every living villager (the records the game loads, statues and bodies left out:
  scripts/vvfp_consistency_check.py), their sex, age, looks, family number and, in The Lost
  Children to New Believers, both parents as the game keeps them on the child's own record;
* the patcher's logs for the slot's current village: the Births and Conceptions log (who was born
  to whom, and which babies came together), every Village History / Population snapshot's
  "Parents:" (the save's parent fields at each save), and the Deaths, Disappeared, Arrived and
  Unaccounted records (who is gone, and how old they were).

A villager is known by name, head and body, as every one of those records names them.  Anyone
whose parents no record names is a founder of the family tree (generation I): the village's
first villagers, island-event arrivals, and villagers born before the logs began.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

import vv_log_tools as tools

UNITS_PER_YEAR = 20

# The age window the helper pairs by default (the owner: "only people 18-49").
YOUNGEST_YEARS = 18
OLDEST_YEARS = 49

# New Believers keeps a villager's faction in the saved entry's header (+1; 0 = the player's
# own tribe, otherwise a Heathen): Heathens are not the player's to pair.
VV5_FACTION_FROM_NAME = -0x1F
# How many babies an expecting mother carries, from her name in the saved record: the litter the
# game sets at conception (native/parentage_export GAME_LAYOUTS: +0x35C, +0x544, +0xE90, +0x1C50,
# +0x1C50 against the names at +0x370, +0x564, +0xDD4, +0x1B9C, +0x1B9C).  A New Home and The Lost
# Children leave it 0 for one baby.
LITTER_FROM_NAME = {1: -0x14, 2: -0x20, 3: 0xBC, 4: 0xB4, 5: 0xB4}


class GenealogyError(Exception):
    """The family could not be read; the message says why."""


Key = tuple  # (name, head, body)


@dataclass
class Person:
    id: int
    name: str
    head: int | None
    body: int | None
    sex: str | None = None              # "Male" / "Female"
    age: int | None = None              # game units: now, or at death
    alive: bool = False
    gone: str = ""                      # "died", "disappeared", "left" -- or "" (alive / unknown)
    father: int | None = None
    mother: int | None = None
    litter: int | None = None           # babies born together share one number
    family: int | None = None           # the save's family number (the last name's), living only
    expecting: bool = False             # a living mother-to-be
    heathen: bool = False               # New Believers: a current Heathen
    arrived: bool = False               # an Arrived record names them
    how: str = ""                       # the Arrived record's "How" ("Founder", an event's title...)
    first_seen: str | None = None       # the earliest History snapshot (or Arrived record) naming them
    upcoming: bool = False              # a baby on the way (its mother is expecting)
    birth_record: int | None = None     # its Birth record's place in the Births log (birth order)
    generation: int = 1
    number: int | None = None           # its place in the whole tree, oldest first (number_people)
    old_looks: list[tuple[int, int]] = field(default_factory=list)   # (head, body) before Change Appearance

    @property
    def key(self) -> Key:
        return (self.name, self.head, self.body)

    @property
    def years(self) -> int | None:
        return None if self.age is None else self.age // UNITS_PER_YEAR

    def age_text(self) -> str:
        if self.age is None:
            return "age unknown"
        text = f"{self.age} game units ({self.years} years old)"
        return f"died at {text}" if self.gone == "died" else text

    def order_key(self) -> tuple:
        """Oldest first: who appeared in the logs first, then who was born first (the Births log
        is written in birth order), then the older."""
        return (self.upcoming, (self.first_seen or "")[:16], self.birth_record if self.birth_record is not None else -1,
                -(self.age or 0), self.name)


@dataclass
class Village:
    game: int
    slot: int
    tribe: str
    people: dict[int, Person]
    notes: list[str] = field(default_factory=list)
    snapshot_dates: list[str] = field(default_factory=list)     # the History snapshots read
    base_generation: dict[int, int] = field(default_factory=dict)   # each one's, as the records say
    relooked: dict[Key, Key] = field(default_factory=dict)     # an old look's key -> the villager's key now
    full_names: dict[Key, str] = field(default_factory=dict)  # a cut name's key -> the full name shown

    def living(self) -> list[Person]:
        return [p for p in self.people.values() if p.alive]

    def known(self) -> list[Person]:
        """Every villager the records name (the babies on the way are not villagers yet)."""
        return [p for p in self.people.values() if not p.upcoming]

    def children_of(self, pid: int) -> list[Person]:
        return [p for p in self.people.values() if pid in (p.father, p.mother)]


# ---------------------------------------------------------------------------
# Reading the village
# ---------------------------------------------------------------------------

def _i32(data: bytes, at: int) -> int:
    return int.from_bytes(data[at:at + 4], "little", signed=True)


def _cstr(data: bytes, at: int, cap: int) -> str:
    return bytes(data[at:at + cap]).split(b"\0", 1)[0].decode("latin-1")


class _Registry:
    def __init__(self) -> None:
        self.people: dict[int, Person] = {}
        self.by_key: dict[Key, int] = {}
        self.snapshots: dict[str, set[int]] = {}       # History snapshot date -> who it lists
        self.expected: dict[int, Key] = {}             # mother -> the expected father (the save's)
        self.due: dict[int, int] = {}                  # mother -> babies she carries (the save's)
        self.conceptions: dict[Key, tuple] = {}        # mother -> (father key, babies), not born yet
        self.relooked: dict[Key, Key] = {}             # an old look -> the look it changed to
        self.full: dict[Key, Key] = {}                 # a name the Details screen cut -> the full name's key

    def current(self, key: Key) -> Key:
        """The look a villager has now, following their Change Appearance records, under the full name
        the logs keep when the Villager Details screen cut the one in the save (vv_cut_names)."""
        seen = set()
        key = self.full.get(key, key)
        while key in self.relooked and key not in seen:
            seen.add(key)
            key = self.full.get(self.relooked[key], self.relooked[key])
        return key

    def get(self, name: str, head: int | None, body: int | None) -> Person:
        key = self.current((name, head, body))
        if key not in self.by_key:
            pid = len(self.people) + 1
            self.people[pid] = Person(pid, *key)    # the look they have now (Codex, #558)
            self.by_key[key] = pid
        return self.people[self.by_key[key]]


def _save_people(reg: _Registry, folder: Path, game: int, slot: int) -> None:
    """Every living villager the game loads, and (The Lost Children on) the parents the game
    keeps on each child's record."""
    import vv_last_names as ln
    checker = tools.load_checker()
    path = ln.save_path(folder, game, slot)
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise GenealogyError(f"The save {path.name} could not be read: {exc}") from exc
    f = ln.FIELDS[game]
    age_at = -0x28 if game == 1 else checker.LAYOUTS[game].age
    for at in ln._entries(game, data):
        p = reg.get(_cstr(data, at, f.name_cap), _i32(data, at + f.head), _i32(data, at + f.body))
        p.alive = True
        p.sex = "Male" if _i32(data, at + f.sex) == f.male else "Female"
        p.age = _i32(data, at + age_at)
        p.family = _i32(data, at + f.family)
        if game == 1:
            p.expecting = _i32(data, at - 0x370 + 0x358) != 0       # the delivery the game counts down
        elif f.expecting is not None:
            p.expecting = p.sex == "Female" and data[at + f.expecting] != 0
            if p.expecting:
                _fh, _fb, _mh, _mb, eh, eb = f.looks
                reg.expected[p.id] = (_cstr(data, at + f.expecting, f.parent_cap),
                                      _i32(data, at + eh), _i32(data, at + eb))
        litter = _i32(data, at + LITTER_FROM_NAME[game])
        if p.expecting and (litter in (1, 2, 3) or game <= 2 and litter == 0):
            reg.due[p.id] = max(1, litter)
        if game == 5:
            p.heathen = data[at + VV5_FACTION_FROM_NAME] != 0
        if f.father is not None:
            fh, fb, mh, mb, _eh, _eb = f.looks
            for off, head, body, sex in ((f.father, fh, fb, "Male"), (f.mother, mh, mb, "Female")):
                name = _cstr(data, at + off, f.parent_cap)
                if name:
                    parent = reg.get(name, _i32(data, at + head), _i32(data, at + body))
                    parent.sex = parent.sex or sex
                    if sex == "Male":
                        p.father = parent.id
                    else:
                        p.mother = parent.id


PARENT_LINE = re.compile(r"^\s+(Father|Mother): (.*)$")
LOOKS_LINE = re.compile(r"^\s+(Head|Body): (-?\d+)\s*$")


def _snapshot_parents(lines: list[str]) -> dict[str, tuple]:
    """A History / Population entry's "Parents:" section: {"Father": key, "Mother": key}."""
    out: dict[str, tuple] = {}
    k = 0
    while k < len(lines):
        m = PARENT_LINE.match(lines[k])
        if m and lines[k].startswith("    "):
            name, head, body = m.group(2).strip(), None, None
            j = k + 1
            while j < len(lines):
                lm = LOOKS_LINE.match(lines[j])
                if not lm or not lines[j].startswith("      "):
                    break
                if lm.group(1) == "Head":
                    head = int(lm.group(2))
                else:
                    body = int(lm.group(2))
                j += 1
            if name and name not in ("(unknown)", "(none)", "(unnamed)"):
                out[m.group(1)] = (name, head, body)
            k = j
            continue
        k += 1
    return out


def _log_people(reg: _Registry, folder: Path, game: int, slot: int) -> None:
    """The dead and departed, and every parent a snapshot names."""
    import vv_log_additions as additions
    for b in additions.person_blocks(folder, slot, game):
        name, head, body = b.identity
        if not name or head is None or body is None:
            continue
        p = reg.get(name, head, body)
        sex = b.value("Sex")
        if sex in ("Male", "Female") and p.sex is None:
            p.sex = sex
        if b.heading.startswith("Death") and not p.alive:     # reanimated (New Believers): alive again
            p.gone = "died"
            age = b.value("Age at death")
            if age and age.lstrip("-").isdigit():
                p.age = int(age)
        elif b.heading.startswith("Disappeared") and not p.alive:
            p.gone = p.gone or "disappeared"
        elif b.heading.startswith("Arrived") and b.value("Special villager") == "Golden Child":
            # A New Home's Golden Child is born to a mother (its puzzle spends her pregnancy), never an
            # arrival (the owner, 2026-10-08); an older patcher backfilled an Arrived record for it.
            pass
        elif b.heading.startswith("Arrived"):
            p.arrived = True
            p.how = b.value("How") or p.how
            seen = re.search(r"first seen (\d{4}-\d{2}-\d{2} \d{2}:\d{2})", b.value("Age at arrival") or "")
            if seen and (p.first_seen is None or seen.group(1) < p.first_seen[:16]):
                p.first_seen = seen.group(1)
        if b.date and b.heading.startswith("Villager ") and not additions.is_population(b.path):
            reg.snapshots.setdefault(b.date, set()).add(p.id)
            if p.first_seen is None or b.date < p.first_seen:
                p.first_seen = b.date
        age = b.value("Age")
        if age and age.lstrip("-").isdigit() and not p.alive and p.gone != "died":
            p.age = max(p.age or 0, int(age))
        parents = _snapshot_parents(b.lines)
        for label, sex, attr in (("Father", "Male", "father"), ("Mother", "Female", "mother")):
            if label in parents and getattr(p, attr) is None:
                parent = reg.get(*parents[label])
                parent.sex = parent.sex or sex
                setattr(p, attr, parent.id)


def _births(reg: _Registry, folder: Path, game: int, slot: int) -> None:
    """The Births and Conceptions log: each child's parents, and the babies born together."""
    import vv_log_additions as additions
    checker = tools.load_checker()
    villages = additions.current_villages(folder, game, slot)
    # Every name the village has had (Codex, #555: the records before a Rename Tribe).
    records, _files = checker.births_log(folder, game, slot, villages if villages is not None else "every")
    litter_no = 0
    last: tuple | None = None           # (mother key, litter number, babies so far, how many it holds)
    for index, rec in enumerate(records):
        if rec.kind == "conception" and rec.mother is not None and rec.mother.name:
            # Under the looks the parents have now, so a mother's Change Appearance since
            # conception does not lose the father or the litter (Codex, #558).
            mother = reg.current((rec.mother.name, rec.mother.head, rec.mother.body))
            father = rec.father and reg.current((rec.father.name, rec.father.head, rec.father.body))
            reg.conceptions[mother] = (father if father and father[0] else None, rec.babies or 1)
        if rec.kind != "birth" or rec.child is None or not rec.child.name:
            last = None
            continue
        reg.conceptions.pop(reg.current((rec.mother.name, rec.mother.head, rec.mother.body)) if rec.mother else None,
                            None)
        child = reg.get(rec.child.name, rec.child.head, rec.child.body)
        if child.birth_record is None:
            child.birth_record = index
        for person, attr, sex in ((rec.father, "father", "Male"), (rec.mother, "mother", "Female")):
            if person is not None and person.name:
                parent = reg.get(person.name, person.head, person.body)
                parent.sex = parent.sex or sex
                if getattr(child, attr) is None:
                    setattr(child, attr, parent.id)
        mother = rec.mother and (rec.mother.name, rec.mother.head, rec.mother.body)
        # A delivery's Birth records are written one after another, its Conception before them;
        # three babies at most.  A "Born as:" line, where Repair Saves & Logs wrote one, says how many came
        # together (Codex, #555): a single birth joins no other.
        size = rec.born_as or 3
        if last is not None and mother is not None and last[0] == mother and last[2] < last[3] \
                and rec.born_as in (0, last[3]) and size > 1:
            litter_no, count = last[1], last[2] + 1
        else:
            litter_no, count = litter_no + 1, 1
        child.litter = litter_no
        last = (mother, litter_no, count, size) if mother is not None else None
    # One baby alone is no litter.
    sizes: dict[int, int] = {}
    for p in reg.people.values():
        if p.litter is not None:
            sizes[p.litter] = sizes.get(p.litter, 0) + 1
    for p in reg.people.values():
        if p.litter is not None and sizes[p.litter] < 2:
            p.litter = None


def load_village(folder: Path, game: int, slot: int, full_names: bool = True) -> Village:
    """The slot's village, its living villagers and every relative the save and logs know.

    With `full_names` (the Family Tree Maker and the Village Matchmaker), a living villager whose name
    the Villager Details screen cut is the same villager as the logs' record of their full name, and
    is shown by it (the owner, 2026-10-07: "Family trees will use the full names from the logs, then
    the save data").  Without (Last Names, Number Duplicate Names: they rename the save and the logs,
    so they work from the names as written), everyone keeps the name the records carry."""
    import vv_log_additions as additions
    import vv_tribe_rename
    folder = Path(folder)
    reg = _Registry()
    notes: list[str] = []
    if full_names:
        # Before anything is read, so the save's record, its parent fields and every log line naming
        # the cut name with the villager's looks all land on the one person under the full name.
        import vv_cut_names
        import vv_last_names as ln
        try:
            cuts, _undecided = vv_cut_names.find_cut(folder, game, slot)
        except (ln.LastNamesError, OSError, ValueError):
            cuts = []                           # the tree is still drawn, from the names as written
        for cut in cuts:
            v = cut.villager
            reg.full[v.identity] = (cut.full, v.head, v.body)
    _appearance_changes(reg, folder, game, slot)
    _save_people(reg, folder, game, slot)
    _births(reg, folder, game, slot)
    _log_people(reg, folder, game, slot)
    checker = tools.load_checker()
    exact, by_name = checker.known_sexes(folder, game)
    for p in reg.people.values():
        if p.sex is None:
            p.sex, _source = checker.sex_for(game, {"name": p.name, "head": p.head, "body": p.body},
                                             exact, by_name)
    import vv_last_names as ln
    tribe = ""
    try:
        games = {g.number: g for g in vv_tribe_rename.GAMES}
        tribe = vv_tribe_rename.save_name(games[game], ln.save_path(folder, game, slot).read_bytes()) or ""
    except (OSError, KeyError, ValueError):
        pass
    _upcoming(reg)
    village = Village(game, slot, tribe, reg.people, notes, sorted(reg.snapshots))
    village.relooked = {old: reg.current(old) for old in reg.relooked if reg.current(old) != old}
    village.full_names = {cut: full[0] for cut, full in reg.full.items()}
    for old, now in village.relooked.items():
        if now in reg.by_key:
            reg.people[reg.by_key[now]].old_looks.append((old[1], old[2]))
    _generations(village, reg.snapshots)
    number_people(village)
    if additions.current_villages(folder, game, slot) is None:
        notes.append("The save's tribe name could not be read, so records of every village this "
                     "slot has held were read.")
    return village


def _appearance_changes(reg: _Registry, folder: Path, game: int, slot: int) -> None:
    """Change Appearance's "Appearance changed" records (the Births and Conceptions log): a record
    naming the villager with an old look is the same villager as the one with the new look (the
    owner: "regarding appearance changes, sure. Log those.").  In log order, so a later change wins;
    a change back makes the old look the villager's own again."""
    import vv_log_additions as additions
    checker = tools.load_checker()
    villages = additions.current_villages(folder, game, slot)
    births = [path for path in checker.log_files(folder) if "Births and Conceptions" in path.name]
    for path in sorted(births, key=lambda q: [int(s) if s.isdigit() else s for s in re.split(r"(\d+)", q.name)]):
        for b in additions.blocks(path):
            if b.heading != "Appearance changed" or not b.of(slot, game, villages):
                continue
            values = [b.value(label) for label in ("Old head", "Old body", "New head", "New body")]
            name = b.value("Name")
            if not name or not all(v and v.lstrip("-").isdigit() for v in values):
                continue
            old_head, old_body, new_head, new_body = (int(v) for v in values)
            old, new = (name, old_head, old_body), (name, new_head, new_body)
            reg.relooked.pop(new, None)
            reg.relooked[old] = new


def _upcoming(reg: _Registry) -> None:
    """A baby on the way for every expecting mother (the owner: "another child with a diamond
    portrait"): the father the save keeps for her (The Lost Children on) or her last Conception
    record's, and as many babies as her saved record says she carries (twins and triplets), else
    as that Conception record says."""
    n = 0
    for mother in [p for p in reg.people.values() if p.alive and p.expecting]:
        father_key, babies = reg.conceptions.get(mother.key, (None, 1))
        babies = reg.due.get(mother.id, babies)
        father_key = reg.expected.get(mother.id, father_key)
        father = reg.get(*father_key) if father_key and father_key[0] else None
        if father is not None:
            father.sex = father.sex or "Male"
        n += 1
        litter = -n if babies > 1 else None
        for k in range(max(1, min(3, babies))):
            baby = reg.get("Upcoming child", -n, -k - 1)
            baby.upcoming, baby.mother, baby.litter = True, mother.id, litter
            baby.father = father.id if father is not None else None


# How the tree's rows are ordered and numbered (the owner: "By appearance (default), By age,
# whatever else is logical").
SORTS = {
    "appearance": "By appearance in the tribe",
    "age": "By age (oldest first)",
    "family": "By family (brothers and sisters together)",
    "name": "By name",
}


def number_people(village: Village, sort: str = "appearance") -> None:
    """Every villager's number (the owner: "number every villager ... do not restart numbering at
    any point.  Number all of gen 1, then gen 2"): generation by generation, in the chosen order.
    A baby on the way has none yet, and comes last in its row."""
    n = 0
    people = village.people
    for g in sorted({p.generation for p in village.known()}):
        row = [p for p in village.known() if p.generation == g]
        if sort == "age":
            row.sort(key=lambda q: (-(q.age or 0), q.order_key()))
        elif sort == "name":
            row.sort(key=lambda q: (q.name.casefold(), q.order_key()))
        elif sort == "family":
            def family_key(q: Person) -> tuple:
                parents = sorted(people[r].number or 0 for r in (q.mother, q.father) if r is not None)
                return (tuple(parents) or (0,), q.order_key())
            row.sort(key=family_key)
        else:
            row.sort(key=lambda q: q.order_key())
        for p in row:
            n += 1
            p.number = n


def snapshot_dates(village: Village) -> list[str]:
    return list(village.snapshot_dates)


def is_arrival(p: Person, first_snapshot: str | None) -> bool:
    """Someone with no recorded parent who joined the village: an Arrived record says how (not
    "Founder"), or they first appear after the village's first History snapshot."""
    if p.father is not None or p.mother is not None or p.upcoming:
        return False
    if p.arrived and p.how:
        return p.how != "Founder"
    return p.first_seen is not None and first_snapshot is not None and p.first_seen[:16] > first_snapshot[:16]


def _generations(village: Village, snapshots: dict[str, set[int]]) -> None:
    """Generation I: the founders.  An arrival is in the generation they first appear in (the owner:
    "do not put arrivals in the same generation with the founders"): the newest generation among
    the villagers the History snapshot of their arrival lists.  A child is one below the later of
    its parents."""
    people = village.people
    dates = sorted(snapshots)
    first = dates[0] if dates else None
    arrivals = [pid for pid, p in people.items() if is_arrival(p, first)]
    base = {pid: 1 for pid in arrivals}

    def compute() -> dict[int, int]:
        done: dict[int, int] = {}

        def gen(pid: int, path: frozenset) -> int:
            if pid in done:
                return done[pid]
            p = people[pid]
            parents = [q for q in (p.father, p.mother) if q is not None and q not in path]
            value = 1 + max((gen(q, path | {pid}) for q in parents), default=0) if parents else base.get(pid, 1)
            done[pid] = value
            return value

        for pid in people:
            gen(pid, frozenset())
        return done

    def descendants(pid: int) -> set[int]:
        out, frontier = set(), [pid]
        while frontier:
            q = frontier.pop()
            for c in people.values():
                if q in (c.father, c.mother) and c.id not in out:
                    out.add(c.id)
                    frontier.append(c.id)
        return out

    same_time = {}
    for pid in arrivals:
        when = people[pid].first_seen
        snap = next((d for d in dates if when is not None and d[:16] >= when[:16]), None)
        same_time[pid] = snap
    later = {pid: descendants(pid) for pid in arrivals}
    gens = compute()
    for _round in range(len(arrivals) + 1):
        changed = False
        for pid in arrivals:
            snap = same_time[pid]
            if snap is None:
                continue
            joined = {q for q, s in same_time.items() if s == snap}
            present = snapshots[snap] - joined - later[pid]
            value = max((gens[q] for q in present), default=1)
            if base[pid] != value:
                base[pid] = value
                changed = True
        if not changed:
            break
        gens = compute()
    for pid, value in gens.items():
        people[pid].generation = value
    village.base_generation = dict(gens)


# ---------------------------------------------------------------------------
# Relatedness
# ---------------------------------------------------------------------------

class Kinship:
    """Coefficients of kinship over the recorded family (Wright): two villagers' chance of
    sharing a gene by descent.  Twice it is how related they are: 1/2 a parent, child or full
    sibling, 1/4 a half sibling, grandparent, aunt or uncle, 1/8 a first cousin."""

    def __init__(self, village: Village) -> None:
        self.people = village.people
        # The records' generations: the family tree's "Move to generation" only changes where a
        # villager is drawn, never who descends from whom (Codex, #555).
        self.generation = village.base_generation
        self.memo: dict[tuple[int, int], Fraction] = {}

    def _order(self, pid: int) -> tuple:
        return (self.generation.get(pid, self.people[pid].generation), pid)

    def phi(self, a: int, b: int) -> Fraction:
        if a == b:
            p = self.people[a]
            inbred = self.phi(p.father, p.mother) if p.father and p.mother else Fraction(0)
            return (1 + inbred) / 2
        if self._order(a) < self._order(b):
            a, b = b, a
        key = (a, b)
        if key not in self.memo:
            p = self.people[a]
            total = Fraction(0)
            for parent in (p.father, p.mother):
                if parent is not None:
                    total += self.phi(parent, b)
            self.memo[key] = total / 2
        return self.memo[key]

    def relatedness(self, a: int, b: int) -> Fraction:
        return 2 * self.phi(a, b)


def ancestors(village: Village, pid: int) -> dict[int, int]:
    """Every recorded ancestor and how many generations back the nearest path to them is."""
    out: dict[int, int] = {}
    frontier = [(pid, 0)]
    while frontier:
        nxt = []
        for q, depth in frontier:
            p = village.people[q]
            for parent in (p.father, p.mother):
                if parent is not None and (parent not in out or out[parent] > depth + 1):
                    out[parent] = depth + 1
                    nxt.append((parent, depth + 1))
        frontier = nxt
    return out


ORDINAL = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth"}
REMOVED = {1: "once", 2: "twice", 3: "three times"}


def relationship(village: Village, a: int, b: int) -> str:
    """How two villagers are related, by their nearest common ancestor (as the records know it)."""
    pa, pb = village.people[a], village.people[b]
    up_a, up_b = ancestors(village, a), ancestors(village, b)
    if b in up_a or a in up_b:
        older, younger, depth = (b, a, up_a[b]) if b in up_a else (a, b, up_b[a])
        names = {1: "parent and child", 2: "grandparent and grandchild"}
        return names.get(depth, f"{'great-' * (depth - 2)}grandparent and grandchild")
    shared_parents = {pa.father, pa.mother} & {pb.father, pb.mother} - {None}
    if shared_parents:
        both = pa.father and pa.mother and {pa.father, pa.mother} == {pb.father, pb.mother}
        if both and pa.litter is not None and pa.litter == pb.litter:
            return "twins" if sum(1 for p in village.people.values() if p.litter == pa.litter) == 2 \
                else "triplets"
        return "full siblings" if both else "half siblings"
    common = set(up_a) & set(up_b)
    if not common:
        return "no recorded common ancestor"
    # The nearest: fewest generations between them all told (Codex, #555: two up and two down,
    # first cousins, is nearer than one up and three down).
    da, db = min(((up_a[c], up_b[c]) for c in common), key=lambda d: (d[0] + d[1], max(d), d))
    near, far = sorted((da, db))
    if near == 1:
        return f"{'great-' * (far - 2)}aunt or uncle and niece or nephew"
    degree, removed = near - 1, far - near
    # Double cousins: each of one's parents is related to a different parent of the other (a
    # brother and sister married to a sister and brother), so two couples are the nearest common
    # ancestors, not one.
    nearest = {c for c in common if (up_a[c], up_b[c]) == (da, db)}
    double = "double " if len(nearest) >= 4 else ""
    text = f"{double}{ORDINAL.get(degree, f'{degree}th')} cousins"
    if removed:
        text += f", {REMOVED.get(removed, f'{removed} times')} removed"
    return text


# ---------------------------------------------------------------------------
# The rules and the pairs
# ---------------------------------------------------------------------------

@dataclass
class Rules:
    """Every rule is the player's toggle.  The defaults are only where the window starts."""
    plan_ahead: bool = False            # any age (children included), to plan ahead
    allow_50_plus: bool = False         # the 18-49 window, and 50 and older too
    close_in_age: bool = True
    max_age_gap_years: int = 10
    no_shared_ancestors: bool = True
    shared_ancestor_generations: int = 0    # 0: since the tribe began; else within the last N
    max_relatedness: bool = True
    max_relatedness_percent: float = 3.125  # second cousins
    block_parent_child: bool = True
    block_full_siblings: bool = True
    block_half_siblings: bool = False
    block_grandparent: bool = False
    block_aunt_uncle: bool = False
    block_first_cousins: bool = False
    not_expecting: bool = True
    different_last_name: bool = True
    one_family_per_partner: bool = True   # no partner from a family they already have a child with
    prefer_fresh_blood: bool = True

    def describe(self) -> list[str]:
        out = []
        if self.plan_ahead:
            out.append("Any age (planning ahead)")
        else:
            out.append(f"Aged {YOUNGEST_YEARS} or older" if self.allow_50_plus
                       else f"Aged {YOUNGEST_YEARS}-{OLDEST_YEARS}")
        if self.close_in_age:
            out.append(f"At most {self.max_age_gap_years} years apart in age")
        if self.no_shared_ancestors:
            out.append("No shared ancestor" + (f" within the last {self.shared_ancestor_generations} generations"
                                               if self.shared_ancestor_generations else " since the tribe began"))
        if self.max_relatedness:
            out.append(f"Related by at most {self.max_relatedness_percent:g}%")
        for flag, words in ((self.block_parent_child, "No parent and child"),
                            (self.block_full_siblings, "No full siblings"),
                            (self.block_half_siblings, "No half siblings"),
                            (self.block_grandparent, "No grandparent and grandchild"),
                            (self.block_aunt_uncle, "No aunt or uncle and niece or nephew"),
                            (self.block_first_cousins, "No first cousins"),
                            (self.not_expecting, "Not already expecting"),
                            (self.different_last_name, "Different last names (family)"),
                            (self.one_family_per_partner, "One Family Per Partner"),
                            (self.prefer_fresh_blood, "Fresh blood first")):
            if flag:
                out.append(words)
        return out


@dataclass
class Pair:
    man: Person
    woman: Person
    related: Fraction
    relation: str
    shared: int                          # recorded ancestors they share

    @property
    def percent(self) -> float:
        return float(self.related) * 100


def _age_ok(p: Person, rules: Rules) -> bool:
    if rules.plan_ahead:
        return True
    years = p.years
    if years is None or years < YOUNGEST_YEARS:
        return False
    return rules.allow_50_plus or years <= OLDEST_YEARS


def candidates(village: Village, rules: Rules) -> tuple[list[Person], list[Person]]:
    """The men and the women the rules let pair at all."""
    men, women = [], []
    for p in sorted(village.living(), key=lambda q: -(q.age or 0)):
        if p.heathen or p.sex not in ("Male", "Female") or not _age_ok(p, rules):
            continue
        # A New Home's Golden Child (family 199) is 5 years old for life and never breeds: the game's
        # breeding check (0x42E5A4) refuses it (the owner: "GOLDEN CHILD IS A SPECIAL EXCEPTION TO
        # EVERYTHING").
        if village.game == 1 and p.family == 199:
            continue
        if p.sex == "Female" and rules.not_expecting and p.expecting:
            continue
        (men if p.sex == "Male" else women).append(p)
    return men, women


def _last_name(name: str) -> str:
    """The last name a name carries: its last word that is not Number Duplicate Names' numeral, and
    never the first word (the game's own names are one word) -- "Soda Akikai II" is an Akikai, and
    "Soda II" has none."""
    words = name.split()
    while len(words) > 1 and re.fullmatch(r"[IVXLCDM]+", words[-1]):
        words.pop()
    return words[-1] if len(words) > 1 else ""


def _same_last_name(man: Person, woman: Person) -> bool:
    """Whether the two share a last name: the last names they carry when both have one (Repair Saves & Logs
    gives them, from the game's list, a parent's or the player's own), else the game's family
    number -- which a founder, a newcomer or an arrival, unrelated for all intents and purposes (the
    owner), only shares with someone by chance."""
    names = [_last_name(p.name) for p in (man, woman)]
    names = [n for n in names if n]
    if len(names) == 2:
        return names[0].casefold() == names[1].casefold()
    return (man.family is not None and man.family == woman.family
            and not any(p.father is None and p.mother is None for p in (man, woman)))


def _blocked(rules: Rules, man: Person, woman: Person, relation: str, related: Fraction,
             shared: dict, partners: dict[int, set[str]] | None = None) -> str | None:
    if rules.close_in_age and man.age is not None and woman.age is not None \
            and abs(man.age - woman.age) > rules.max_age_gap_years * UNITS_PER_YEAR:
        return "too far apart in age"
    if rules.block_parent_child and relation == "parent and child":
        return relation
    if rules.block_full_siblings and relation in ("full siblings", "twins", "triplets"):
        return relation
    if rules.block_half_siblings and relation == "half siblings":
        return relation
    if rules.block_grandparent and "grandparent" in relation:
        return relation
    if rules.block_aunt_uncle and "aunt or uncle" in relation:
        return relation
    if rules.block_first_cousins and relation.removeprefix("double ").startswith("first cousins"):
        return relation
    if rules.no_shared_ancestors and shared:
        depth = rules.shared_ancestor_generations
        if not depth or any(max(da, db) <= depth for da, db in shared.values()):
            return "shared ancestor"
    if rules.max_relatedness and float(related) * 100 > rules.max_relatedness_percent + 1e-9:
        return "too closely related"
    # A founder, a newcomer or an arrival is an unrelated individual for all intents and purposes (the
    # owner): a family number they share with someone by chance is not a family.
    if rules.different_last_name and _same_last_name(man, woman):
        return "same last name"
    # A family is a family whatever its numbers (the owner): a villager who already has a child with a
    # Wanjiko is not offered a Wanjiko II.
    if rules.one_family_per_partner and partners is not None and (
            _last_name(woman.name).casefold() in partners.get(man.id, ())
            or _last_name(man.name).casefold() in partners.get(woman.id, ())):
        return "already has a child with that family"
    return None


def _partner_families(village: Village) -> dict[int, set[str]]:
    """Each parent -> the last names (numbers dropped) of everyone they have a child, born or on the
    way, with."""
    out: dict[int, set[str]] = {}
    for child in village.people.values():
        if child.father is None or child.mother is None:
            continue
        for one, other in ((child.father, child.mother), (child.mother, child.father)):
            name = _last_name(village.people[other].name).casefold()
            if name:
                out.setdefault(one, set()).add(name)
    return out


def suggest(village: Village, rules: Rules) -> tuple[list[Pair], dict[int, list[Pair]], list[Pair]]:
    """(one-to-one suggested pairs, every allowed partner per woman, the least related pairs when
    the rules allow none).  Pairs are ranked least related first, then fresh blood (with that rule),
    then closest in age."""
    kin = Kinship(village)
    men, women = candidates(village, rules)
    allowed: list[Pair] = []
    every: list[Pair] = []
    up = {p.id: ancestors(village, p.id) for p in men + women}
    partners = _partner_families(village)
    for w in women:
        for m in men:
            related = kin.relatedness(m.id, w.id)
            relation = relationship(village, m.id, w.id)
            common = {c: (up[m.id][c], up[w.id][c]) for c in set(up[m.id]) & set(up[w.id])}
            pair = Pair(m, w, related, relation, len(common))
            every.append(pair)
            if _blocked(rules, m, w, relation, related, common, partners) is None:
                allowed.append(pair)

    def fresh(p: Person) -> int:
        return 0 if p.father is None and p.mother is None else 1

    def rank(pair: Pair) -> tuple:
        gap = abs((pair.man.age or 0) - (pair.woman.age or 0))
        return (pair.related, (fresh(pair.man) + fresh(pair.woman)) if rules.prefer_fresh_blood else 0,
                pair.shared, gap, pair.woman.id, pair.man.id)

    allowed.sort(key=rank)
    per_woman: dict[int, list[Pair]] = {}
    for pair in allowed:
        per_woman.setdefault(pair.woman.id, []).append(pair)
    # One partner each for as many as the rules allow (Codex, #555: taking the best pair first can
    # leave a woman unpaired whom another choice would have paired): each woman, best placed first,
    # takes her best free man, or one whose partner can move to another of hers.
    partner: dict[int, Pair] = {}           # man -> his pair

    def place(woman: int, seen: set) -> bool:
        for pair in per_woman.get(woman, []):
            if pair.man.id in seen:
                continue
            seen.add(pair.man.id)
            if pair.man.id not in partner or place(partner[pair.man.id].woman.id, seen):
                partner[pair.man.id] = pair
                return True
        return False

    for woman in sorted(per_woman, key=lambda w: rank(per_woman[w][0])):
        place(woman, set())
    one_to_one = sorted(partner.values(), key=rank)
    fallback = [] if allowed else sorted(every, key=rank)[:10]
    return one_to_one, per_woman, fallback


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------

ROMAN = ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
         (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"))


def roman(n: int) -> str:
    out = ""
    for value, letters in ROMAN:
        count, n = divmod(n, value)
        out += letters * count
    return out


# Number Duplicate Names' orders: who is "I" (the owner: "the oldest person with a duplicate name should
# be named "I" unless the player says otherwise").
NUMBER_ORDERS = {
    "oldest": "Oldest first",
    "youngest": "Youngest first",
    "appearance": "In order of appearance",
}


def duplicate_names(village: Village, order: str = "appearance", reserved: set[str] = frozenset(),
                    leave: set[int] = frozenset(), weight: dict[int, int] | None = None) -> dict[int, str]:
    """Each villager who shares a name with another, numbered (the owner, 2026-10-07: "If there are
    duplicate "Soda"s, name the first one "Soda I", and the second one "Soda II" etc."), the dead
    too, in the NUMBER_ORDERS order: by age (the age now, or at death; an unknown age last), or as
    they appeared in the records.  A baby on the way has no name yet.  A number that would give a
    name already in use is passed over (Codex, #557): a village with a "Soda I" numbers its two
    Sodas II and III.  `reserved`: names in use the village does not hold (records with no looks);
    `leave`: villagers neither numbered nor counted; `weight`: how many villagers one Person stands
    for (namesakes who look alike, which the records cannot tell apart), so the next one is numbered
    after all of them (Codex, #557)."""
    keys = {
        "oldest": lambda p: (p.age is None, -(p.age or 0), p.order_key()),
        "youngest": lambda p: (p.age is None, p.age or 0, p.order_key()),
        "appearance": Person.order_key,
    }
    holders: dict[str, list[Person]] = {}
    for p in sorted(village.known(), key=keys[order]):
        if p.id not in leave:
            holders.setdefault(p.name, []).append(p)
    taken = set(holders) | set(reserved)
    out = {}
    for name, ps in holders.items():
        if len(ps) < 2:
            continue
        n = 0
        for p in ps:
            n += 1
            while f"{name} {roman(n)}" in taken:
                n += 1
            out[p.id] = f"{name} {roman(n)}"
            taken.add(out[p.id])
            n += (weight or {}).get(p.id, 1) - 1
    return out


def numbered(p: Person) -> str:
    """"#12 Name", or the name alone for one with no number on the tree (taken off it)."""
    return f"#{p.number} {p.name}" if p.number is not None else p.name


def describe_person(village: Village, p: Person) -> str:
    if p.upcoming:
        return f"{p.name} (on the way)"
    bits = [p.name, p.sex or "sex unknown", p.age_text()]
    if not p.alive:
        bits.append({"died": "dead", "disappeared": "disappeared"}.get(p.gone, "no longer in the village"))
    if p.heathen:
        bits.append("Heathen")
    return ", ".join(bits)


def report(village: Village, game_title: str) -> str:
    """The genealogy: every generation, who descends from whom, and everyone in order of appearance."""
    people = village.people
    lines = [f"{game_title} -- Genealogy",
             f"Village: {village.tribe} (Save {village.slot})" if village.tribe else f"Save {village.slot}",
             "",
             "Generation I is everyone no record gives a parent: the first villagers, island-event "
             "arrivals and villagers born before the patcher's logs began.  A child is one generation "
             "below the later of its parents.  Relatedness counts only the family the save and the logs "
             "record, so ancestry from before the logs began is unknown.",
             ""]
    for note in village.notes:
        lines.append(f"Note: {note}")
    if village.notes:
        lines.append("")
    by_gen: dict[int, list[Person]] = {}
    for p in people.values():
        by_gen.setdefault(p.generation, []).append(p)
    lines.append("== Generations ==")
    for g in sorted(by_gen):
        group = sorted(by_gen[g], key=lambda q: (-(q.age or 0), q.name))
        born = [p for p in group if not p.upcoming]
        coming = len(group) - len(born)
        lines.append(f"Generation {roman(g)}: {len(born)} villagers ({sum(p.alive for p in born)} living)"
                     + (f", {coming} on the way" if coming else ""))
        for p in group:
            parents = [people[q].name for q in (p.father, p.mother) if q is not None]
            lines.append(f"  {describe_person(village, p)}"
                         + (f" -- child of {' and '.join(parents)}" if parents else ""))
            kids = village.children_of(p.id)
            if kids:
                lines.append(f"    children: {', '.join(k.name for k in sorted(kids, key=lambda q: -(q.age or 0)))}")
        lines.append("")
    lines.append("== Everyone, in order of appearance in the tribe ==")
    lines.append("  (the number is the villager's number on the family tree)")
    for p in sorted(village.known(), key=lambda q: q.order_key()):
        if p.father is not None or p.mother is not None:
            parents = " and ".join(people[q].name for q in (p.mother, p.father) if q is not None)
            how = f"born to {parents}"
        elif is_arrival(p, min(snapshot_dates(village), default=None)):
            how = f"arrived ({p.how})" if p.how else "arrived"
        else:
            how = "founder"
        seen = f", first seen {p.first_seen}" if p.first_seen else ""
        lines.append(f"  {p.number if p.number is not None else '-'}. {describe_person(village, p)} -- "
                     f"generation {roman(p.generation)}, "
                     f"{how}{seen}")
    lines.append("")
    return "\n".join(lines)


def pair_report(village: Village, rules: Rules, game_title: str) -> str:
    """The pairing suggestions (their own button: the owner, "get rid of the pairings on the family
    tree.  there should be a separate button for pairing suggestions")."""
    people = village.people
    one_to_one, per_woman, fallback = suggest(village, rules)
    lines = [f"{game_title} -- Village Matchmaker",
             f"Village: {village.tribe} (Save {village.slot})" if village.tribe else f"Save {village.slot}",
             "",
             "Relatedness counts only the family the save and the patcher's logs record; ancestry from "
             "before the logs began is unknown.  The number before a name is its number on the family tree.",
             ""]
    lines.append("== Pairing rules ==")
    lines += [f"  {r}" for r in rules.describe()] or ["  (none)"]
    lines.append("")
    lines.append("== Suggested pairs (each villager once, least related first) ==")
    if one_to_one:
        for n, pair in enumerate(one_to_one, 1):
            lines.append(f"  {n}. {numbered(pair.man)}, {pair.man.age_text()}, and "
                         f"{numbered(pair.woman)}, {pair.woman.age_text()}: {pair.relation}, "
                         f"related {pair.percent:g}%")
    else:
        lines.append("  No pair meets every rule.  The least related pairs available:")
        for pair in fallback:
            lines.append(f"    {pair.man.name} and {pair.woman.name}: {pair.relation}, related {pair.percent:g}%")
    lines.append("")
    lines.append("== Every allowed partner, per woman ==")
    for wid, pairs in per_woman.items():
        lines.append(f"  {people[wid].name}, {people[wid].age_text()}:")
        for pair in pairs:
            lines.append(f"    {pair.man.name}, {pair.man.age_text()}: {pair.relation}, related {pair.percent:g}%")
    lines.append("")
    return "\n".join(lines)
