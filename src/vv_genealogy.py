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

# A New Home's Parents (A New Home) sidecar, "Virtual Villagers 1 Parentage Records - Save <slot>.dat"
# (native/vv1_parentage/vv1_parentage.c): a 12-byte 'VP02' header, 256 roster occupants of 36 bytes
# (gender 1/2, departed, head+1, body+1, family scalar, name[28]) and 256 entries of 92 bytes (father
# head+1/body+1, mother head+1/body+1, the pregnancy stash's father head+1/body+1, 2 spare, then the
# father's, the mother's and the stashed father's names, 28 bytes each); then, when anybody is on it,
# the departed list (src/vv1_parents_restore.py departed_list).
VV1_SIDECAR_MAGIC = b"VP02"
VV1_SIDECAR_NAME = 28
VV1_SIDECAR_OCCUPANT = 36
VV1_SIDECAR_ENTRY = 92
VV1_SIDECAR_SIZE = 12 + 256 * (VV1_SIDECAR_OCCUPANT + VV1_SIDECAR_ENTRY)


class GenealogyError(Exception):
    """The family could not be read; the message says why."""


Key = tuple  # (name, head, body)

# The fathers that stand in when there is no man to name -- each shown as the logs write it, in
# every game that has the mechanism, and never a villager:
#   the games' OWN defaults, string literals in the executables, written onto the mother at
#   conception by an event: The Lost Children's Gong of Wonder "?" (head 0, body 0); The Tree of
#   Life's and New Believers' island-event babies "Joey" (2, 2), "Joey Joerson" with last names;
#   and the patcher's fallback for a birth whose game wrote no father at all (A New Home, whose
#   game keeps none): "Unknown" (0, 0) (the owner, 2026-09-21).
GAME_DEFAULT_FATHERS: dict[int, frozenset] = {
    2: frozenset({("?", 0, 0)}),
    4: frozenset({("Joey", 2, 2), ("Joey Joerson", 2, 2)}),
    # New Believers also has the Heathen Mommy's "Unknown" (2, 2): the new-village code the Heathen Mommy Puzzle
    # Restoration brings back starts her pregnancy with the game's own word "Unknown", head 2, body 2
    # (0x465E00; docs/vv5-heathen-mommy-research.md) -- a name only, never a villager (the owner).
    5: frozenset({("Joey", 2, 2), ("Joey Joerson", 2, 2), ("Unknown", 2, 2)}),
}
FALLBACK_FATHER: Key = ("Unknown", 0, 0)
RUNNING = 38   # the like id of "running" in all five games' preference lists (grant_running.RUNNING)


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
    runner: bool = False                # likes running: the living by their save, the dead by their logs
    likes: list[str] | None = None      # the words they like (the living by their save, the dead by their logs); None = not known
    dislikes: list[str] | None = None   # the words they dislike; None = not known (never guessed)
    arrived: bool = False               # an Arrived record names them
    how: str = ""                       # the Arrived record's "How" ("Founder", an event's title...)
    first_seen: str | None = None       # the earliest History snapshot (or Arrived record) naming them
    upcoming: bool = False              # a baby on the way (its mother is expecting)
    birth_record: int | None = None     # its Birth record's place in the Births log (birth order)
    generation: int = 1
    number: int | None = None           # its place in the whole tree, oldest first (number_people)
    old_looks: list[tuple[int, int]] = field(default_factory=list)   # (head, body) before Change Appearance
    placeholder: bool = False           # a default father, not a villager (is_placeholder_father)
    likes: frozenset | None = None      # the living villager's likes as words (the save's)
    likes_seen: set = field(default_factory=set)     # every likes list a log record gives them (frozensets of words)
    former: list[str] = field(default_factory=list)  # names they had before the player renamed them (RenameQuestion)
    # Every special status or title they hold or ever held, as the Family Tree's automatic marks name them
    # (status_marks; the player's Custom titles by their own words): the save, every log record, the graves
    # and the patcher's own files (_statuses).  A former holder keeps it.
    statuses: list[str] = field(default_factory=list)
    converted: bool = False             # New Believers: a record says they converted from the Heathens
    # New Believers: the faction their latest snapshot gives ((date, "Heathen" / "Believer"), or None), and
    # whether a record says they left the tribe to become a Heathen (is_unconverted_heathen).
    faction_seen: tuple | None = None
    left_heathen: bool = False
    # The jobs they are a Master of ("Farmer", "Doctor"...): the living by the save's skills now (save_masters),
    # the dead by their grave's line (its best skill only).  Current, not ever held: the save keeps no history.
    masters: list[str] = field(default_factory=list)
    # A parent "Hide unconverted Heathens" left off the tree: "Father" / "Mother" -> their name (without_heathens).
    hidden_parents: dict = field(default_factory=dict)
    # Living namesakes (two living villagers of one name, head and body): 1 the oldest, 2 the next...; 0 none.
    namesake_rank: int = 0

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


# ---------------------------------------------------------------------------
# Special statuses: the Family Tree's automatic marks
# ---------------------------------------------------------------------------
# The owner (2026-10-22): "All Tribal Chiefs in VV3 will now be automatically marked under Special Villager
# status", then every special or custom status in all five games -- a former holder keeps it, a villager may
# hold several.  The patcher's own titles (native/shared/special_title.h, the logs' "Special villager:"
# line; vv_graves.TITLE_RANK), in that order; a converted Heathen by the mask colour the logs give
# ("Former Heathen (red mask)" is a "Converted Red Mask Heathen"); the player's Custom titles by their words.
STATUS_ORDER = ("Tribal Chief", "Retired Heathen Chief", "Heathen Chief", "Heathen Mommy", "Heathen Doctor",
                "Heathen Master Scientist", "Heathen Master Builder", "Heathen Master Farmer", "Heathen",
                "Former Heathen Master", "Converted Purple Mask Heathen", "Converted Red Mask Heathen",
                "Converted Orange Mask Heathen", "Converted Blue Mask Heathen", "Former Heathen",
                "Golden Child", "Esteemed Elder", "Scholar")
# The statuses each game can give (the Family Tree's descriptor options shown for that game; a Custom title is
# any game's).  Esteemed Elder in The Tree of Life and New Believers: their graves keep the elder byte.
GAME_STATUSES = {
    1: ("Golden Child",),
    2: ("Esteemed Elder",),
    3: ("Tribal Chief", "Esteemed Elder"),
    4: ("Scholar", "Esteemed Elder"),
    5: ("Retired Heathen Chief", "Heathen Chief", "Heathen Mommy", "Heathen Doctor", "Heathen Master Scientist",
        "Heathen Master Builder", "Heathen Master Farmer", "Heathen", "Former Heathen Master",
        "Converted Purple Mask Heathen", "Converted Red Mask Heathen", "Converted Orange Mask Heathen",
        "Converted Blue Mask Heathen", "Former Heathen", "Esteemed Elder"),
}
NO_TITLE = frozenset({"", "none", "(none)", "-", "unknown", "(unknown)", "(not recorded)"})
_FORMER_TITLE = re.compile(r"^Former Heathen( Master)? \((blue|orange|red|purple) mask\)$", re.I)
# The Former Heathens file's kinds (native/shared/former_heathens.h; vv_lost_titles.FORMER_KINDS) as the logs word them.
FORMER_FILE_TITLES = {0: "Former Heathen (blue mask)", 1: "Former Heathen (orange mask)", 2: "Former Heathen (red mask)",
                      3: "Former Heathen Master (purple mask)", 4: "Retired Heathen Chief"}
CONVERTED_HOW = "Converted from the Heathens"
LEFT_FOR_THE_HEATHENS = "Left the tribe: became a Heathen"     # vv_log_additions.LEFT_FOR_THE_HEATHENS
# Where the save keeps a status, from the villager's name in the saved entry (vv_last_names.FIELDS), as
# special_title.h reads the record: The Lost Children's Esteemed Elder +0x7FC (name +0x564); The Secret
# City's Tribal Chief +0xE80 and its five skills +0xEAC (name +0xDD4); The Tree of Life's five skills
# +0x1C5C (name +0x1B9C).  A New Home's Golden Child is its family number 199 (Person.family).
VV2_ELDER_FROM_NAME = 0x7FC - 0x564
VV3_CHIEF_FROM_NAME = 0xE80 - 0xDD4
VV3_SKILLS_FROM_NAME = 0xEAC - 0xDD4
VV4_SKILLS_FROM_NAME = 0x1C5C - 0x1B9C
MASTER = 88


def status_marks(title: str | None) -> list[str]:
    """The automatic marks one "Special villager" title gives (none for no title)."""
    t = (title or "").strip()
    if t.lower() in NO_TITLE:
        return []
    m = _FORMER_TITLE.match(t)
    if m:
        return (["Former Heathen Master"] if m.group(1) else []) + [f"Converted {m.group(2).capitalize()} Mask Heathen"]
    return [t]


def _values(text: str | None) -> list[str]:
    """A record line's values: an Island Events change ("old -> new") gives both, as both were held."""
    return [part.strip() for part in (text or "").split("->") if part.strip().lower() not in NO_TITLE]


def _add_status(p: Person, labels) -> None:
    for label in labels:
        if label and label not in p.statuses:
            p.statuses.append(label)


def _sorted_statuses(labels: list[str]) -> list[str]:
    """The game's titles in their order, then the player's own titles as they were found."""
    return sorted(labels, key=lambda s: (STATUS_ORDER.index(s) if s in STATUS_ORDER else len(STATUS_ORDER),
                                         labels.index(s)))


def save_statuses(game: int, data: bytes, at: int, family: int | None = None) -> list[str]:
    """The statuses the save itself keeps on a living villager (their name at `at`)."""
    import struct
    out = []
    try:
        if game == 1 and family == 199:
            out.append("Golden Child")
        elif game == 2 and data[at + VV2_ELDER_FROM_NAME]:
            out.append("Esteemed Elder")
        elif game == 3:
            if data[at + VV3_CHIEF_FROM_NAME]:
                out.append("Tribal Chief")
            if sum(v >= MASTER for v in struct.unpack_from("<5i", data, at + VV3_SKILLS_FROM_NAME)) >= 3:
                out.append("Esteemed Elder")
        elif game == 4 and all(v >= MASTER for v in struct.unpack_from("<5f", data, at + VV4_SKILLS_FROM_NAME)):
            out.append("Scholar")
    except (IndexError, struct.error):
        pass
    return out


# Each skill's job word, as the graves and the game's Details screen name a Master of it (vv_graves.LAYOUTS jobs).
JOB_OF_SKILL = {"Farming": "Farmer", "Parenting": "Parent", "Healing": "Doctor", "Research": "Scientist",
                "Building": "Builder", "Devotion": "Devotee"}


def save_masters(game: int, data: bytes, at: int) -> list[str]:
    """The jobs a living villager (their name at `at`) is a Master of now: each skill the save keeps at the
    game's Master level or above (vv_corrupt_skills.SKILLS; vv_graves.LAYOUTS master: 90 in A New Home, 88
    in the others), in the game's own skill order."""
    import struct
    import vv_corrupt_skills as cs
    import vv_graves
    names = cs.SKILL_NAMES[game]
    off, is_float = cs.SKILLS[game]
    try:
        values = struct.unpack_from(f"<{len(names)}{'f' if is_float else 'i'}", data, at + off)
    except struct.error:
        return []
    level = vv_graves.LAYOUTS[game].master
    return [JOB_OF_SKILL[name] for name, value in zip(names, values) if level <= value <= 100]


def _merge_faction(p: Person, q: Person) -> None:
    """The older record `p`'s faction facts kept on `q`, the same villager."""
    q.converted = q.converted or p.converted
    q.left_heathen = q.left_heathen or p.left_heathen
    if p.faction_seen and (q.faction_seen is None or p.faction_seen[0] > q.faction_seen[0]):
        q.faction_seen = p.faction_seen


def converted_heathen(p: Person) -> bool:
    """Whether anything says they converted from the Heathens: a converted arrival, a Former Heathen or Retired
    Heathen Chief title (the logs, or New Believers' Former Heathens file)."""
    return p.converted or any(s.startswith(("Converted ", "Former Heathen")) or s == "Retired Heathen Chief"
                              for s in p.statuses)


def is_unconverted_heathen(p: Person) -> bool:
    """New Believers: a Heathen now -- the save's faction for the living, else their latest snapshot's (a
    "Left the tribe: became a Heathen" record when no snapshot says) -- with nothing saying they converted."""
    if p.upcoming or converted_heathen(p):
        return False
    if p.alive:
        return p.heathen
    if p.faction_seen is not None:
        return p.faction_seen[1] == "Heathen"
    # No record says their faction: a "Left the tribe" record, or a Heathen role title from anywhere (a
    # grave's too) -- only a current Heathen holds one (vv_log_additions.HEATHEN_ROLES).
    import vv_log_additions as additions
    return p.left_heathen or any(s in additions.HEATHEN_ROLES for s in p.statuses)


def without_heathens(village: Village) -> Village:
    """The tree's village without its unconverted Heathens (the Family Tree Maker's "Hide unconverted Heathens",
    the owner, 2026-10-22): living, dead and titled Heathens and the babies a hidden Heathen carries left out --
    the tree only; nothing is changed in any file, and the tree's edits for them are kept.  A converted villager
    stays, with their whole history.  A parent so hidden is no longer drawn (no line); the child keeps their
    name in `hidden_parents` ("Father: <name> (Heathen)" in Villager Info)."""
    import dataclasses
    hidden = {pid for pid, p in village.people.items() if is_unconverted_heathen(p)}
    hidden |= {pid for pid, p in village.people.items() if p.upcoming and p.mother in hidden}
    if not hidden:
        return village
    people = {}
    for pid, p in village.people.items():
        if pid in hidden:
            continue
        gone = {label: village.people[q].name for label, q in (("Father", p.father), ("Mother", p.mother))
                if q in hidden}
        people[pid] = dataclasses.replace(p, father=None if p.father in hidden else p.father,
                                          mother=None if p.mother in hidden else p.mother,
                                          hidden_parents={**p.hidden_parents, **gone})
    return dataclasses.replace(village, people=people,
                               base_generation={k: v for k, v in village.base_generation.items() if k not in hidden})


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
    rename_questions: list = field(default_factory=list)       # RenameQuestion: pairs the player has not answered yet
    # IdentityQuestion: an older record and a villager the records cannot say are one villager or two
    # (their looks or title changed, and nothing certain ties them): the Family Tree Maker asks.
    identity_questions: list = field(default_factory=list)
    # ParentQuestion: a parent named by a name and look two living villagers share, both old enough (_parents_by_age).
    parent_questions: list = field(default_factory=list)

    def living(self) -> list[Person]:
        return [p for p in self.people.values() if p.alive]

    def known(self) -> list[Person]:
        """Every villager the records name (the babies on the way are not villagers yet)."""
        return [p for p in self.people.values() if not p.upcoming]

    def villagers(self) -> list[Person]:
        """The villagers the tree numbers and counts: the known, less the default fathers ("?", "Joey",
        "Unknown"), who are names only (the owner, v1.35.85)."""
        return [p for p in self.known() if not getattr(p, "placeholder", False)]

    def children_of(self, pid: int) -> list[Person]:
        return [p for p in self.people.values() if pid in (p.father, p.mother)]


# ---------------------------------------------------------------------------
# Reading the village
# ---------------------------------------------------------------------------

def _i32(data: bytes, at: int) -> int:
    return int.from_bytes(data[at:at + 4], "little", signed=True)


def _cstr(data: bytes, at: int, cap: int) -> str:
    return bytes(data[at:at + cap]).split(b"\0", 1)[0].decode("latin-1")


def _like_words(text: str | None) -> frozenset | None:
    """A log's "Likes:" value as a set of lower-case words (empty for "(none)"); None when the record
    has no such line."""
    if text is None:
        return None
    if not text.strip() or text.strip() == "(none)":
        return frozenset()
    return frozenset(w.strip().lower() for w in text.split(",") if w.strip())


@dataclass
class RenameQuestion:
    """A logged name no living villager has, whose sex, head, body and likes are exactly one living
    villager's (and who is no younger than the record): the player renamed them.  The Family Tree Maker asks
    "Keep <current> or <old>?"; `key` is where the answer is kept (Edits.renames)."""
    old: str
    current: str
    head: int
    body: int
    old_id: int
    current_id: int

    @property
    def key(self) -> str:
        return rename_key(self.old, self.head, self.body)


def rename_key(old: str, head: int, body: int) -> str:
    return f"{old}|{head}|{body}"


@dataclass
class IdentityQuestion:
    """An older record (`older`: a look or title the records name, no villager now has, recorded neither
    dead nor gone) and a villager (`newer`) of the same name the records cannot say are one villager or two:
    nothing proves them two (never listed together, the sex, parents, age and likes fit) and nothing certain
    ties them (no recorded change, no unbroken History, no shared parent).  The Family Tree Maker asks "Is
    <older> the same villager as <newer>?" (Same / Different / Don't know); the answer is kept in Answered
    questions (vv_answered_questions.keep_identity) and every reader honours it."""
    older: Key
    newer: Key
    older_text: str             # what the records say of each: looks, sex, age, where and when seen, parents
    newer_text: str
    why: str                    # what changed, and why it is not certain
    age: int | None = None      # the newer one's age (the list is sorted by it, oldest first)

    @property
    def text(self) -> str:
        return (f"Is {self.older[0]} ({self.older_text}) the same villager as {self.newer[0]} ({self.newer_text})? "
                f"{self.why}")


class _Registry:
    def __init__(self) -> None:
        self.people: dict[int, Person] = {}
        self.by_key: dict[Key, int] = {}
        self.snapshots: dict[str, set[int]] = {}       # History snapshot date -> who it lists
        self.expected: dict[int, Key] = {}             # mother -> the expected father (the save's)
        self.due: dict[int, int] = {}                  # mother -> babies she carries (the save's)
        self.conceptions: dict[Key, tuple] = {}        # mother -> (father key, babies), not born yet
        self.lost: list[tuple[Key, int]] = []          # (mother, babies): "Lost before birth" records
        self.relooked: dict[Key, Key] = {}             # an old look -> the look it changed to
        self.full: dict[Key, Key] = {}                 # a name the Details screen cut -> the full name's key
        # A New Home's living villagers as its save names them: (id, name, gender, family, head, body).
        self.vv1_living: list[tuple] = []
        self.ran: set[int] = set()                     # who a log says likes running
        # NAMESAKES BY THEIR OWN BIRTH (the identity audit): two Birth records of one name and look are
        # two villagers.  key -> every person born with it, the registry's own first; and each person's
        # Birth (record index, father id, mother id), and the parents the save keeps on a living
        # villager's record (The Lost Children on).
        self.namesakes: dict[Key, list[int]] = {}
        self.birth_of: dict[int, tuple] = {}
        self.save_parents: dict[int, tuple] = {}
        self.bodies: set[Key] = set()                  # the dead lying unburied in the save (name, head, body)
        # LIVING NAMESAKES (the owner, v1.35.85: "show both, link by age"): two living villagers of one name,
        # head and body are two people -- one for each of the save's records, never merged.  key -> their ids,
        # in save order (the registry's own first, by_key's); each record names their own parents.
        self.living_dups: dict[Key, list[int]] = {}
        # key -> the earliest History snapshot that lists two villagers of it (when the second one appears).
        self.dup_seen: dict[Key, str] = {}

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
            pid = max(self.people, default=0) + 1      # never a merged-away villager's id again
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
    # The dead lying unburied in the save: each is a villager of their own, never an older look of a living one.
    living_at = set(ln._entries(game, data))
    try:
        reg.bodies = {(_cstr(data, at, f.name_cap), _i32(data, at + f.head), _i32(data, at + f.body))
                      for at in ln._entries(game, data, True) if at not in living_at}
    except (TypeError, ValueError, IndexError):
        reg.bodies = set()
    for at in ln._entries(game, data):
        p = reg.get(_cstr(data, at, f.name_cap), _i32(data, at + f.head), _i32(data, at + f.body))
        if p.alive:
            # A second living record of this name and look is a second villager (its own age, parents, likes:
            # the save's record is the identity), never the first one's record written over.
            first = p
            pid = max(reg.people, default=0) + 1
            p = reg.people[pid] = Person(pid, first.name, first.head, first.body)
            reg.living_dups.setdefault(first.key, [first.id]).append(pid)
        p.alive = True
        p.sex = "Male" if _i32(data, at + f.sex) == f.male else "Female"
        p.age = _i32(data, at + age_at)
        p.family = _i32(data, at + f.family)
        if len(data) >= at + f.likes + 4 * f.slots:
            p.runner = RUNNING in [_i32(data, at + f.likes + 4 * k) for k in range(f.slots)]
        if len(data) >= at + max(f.likes, f.dislikes) + 4 * f.slots:
            import vv_lost_titles as lt         # the games' own like and dislike words, and the save's slots
            prefs = lt._prefs(data, at, game)
            p.likes, p.dislikes = ([w for w in lt.list_text(game, prefs[label]).split(", ") if w != "(none)"]
                                   for label in ("Likes", "Dislikes"))
        if game == 1:
            p.expecting = ln.carrying(game, data, at)       # the delivery the game counts down
            # Who she is in the save's own words, for the Parents (A New Home) sidecar (_vv1_from_sidecar).
            reg.vv1_living.append((p.id, _cstr(data, at, f.name_cap)[:VV1_SIDECAR_NAME - 1],
                                   1 if _i32(data, at + f.sex) == f.male else 2, _i32(data, at + f.family),
                                   _i32(data, at + f.head), _i32(data, at + f.body)))
        elif f.expecting is not None:
            # Her pregnancy field, as the Population log's "Nursing" -- never the expected father's
            # name alone, which the game leaves on her after the delivery (ln.PREGNANCY).
            p.expecting = p.sex == "Female" and ln.carrying(game, data, at)
            if p.expecting and data[at + f.expecting] != 0:
                _fh, _fb, _mh, _mb, eh, eb = f.looks
                reg.expected[p.id] = (_cstr(data, at + f.expecting, f.parent_cap),
                                      _i32(data, at + eh), _i32(data, at + eb))
        litter = _i32(data, at + LITTER_FROM_NAME[game])
        if p.expecting and (litter in (1, 2, 3) or game <= 2 and litter == 0):
            reg.due[p.id] = max(1, litter)
        _add_status(p, save_statuses(game, data, at, p.family))
        p.masters = save_masters(game, data, at)
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
            reg.save_parents[p.id] = (p.father, p.mother)


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


def is_backfilled_arrival(b) -> bool:
    """An Arrived record the arrival backfill wrote with no knowledge of how the villager came --
    "How: unknown" -- which says only that the log had no record of them when it was written.  It
    never outweighs a Birth record of the same villager; an Arrived record with a known "How" (an
    event, a Custom Island Event, a barrel, "Founder") is a real arrival."""
    return b.heading.startswith("Arrived") and (b.value("How") or "").strip().lower() == "unknown"


def _log_people(reg: _Registry, folder: Path, game: int, slot: int) -> None:
    """The dead and departed, and every parent a snapshot names."""
    import vv_log_additions as additions
    import vv_log_decisions as decisions
    # Backfilled Arrived records the player said to remove but chose to leave in the log
    # ("Retroactively edit records?" No): read as if gone (src/vv_log_decisions.py).
    voided = decisions.decided(folder, game, slot, "born_arrived", "remove",
                               additions.current_villages(folder, game, slot))
    listed: dict[tuple, int] = {}               # (snapshot date, living namesakes' key) -> how many it lists
    for b in additions.person_blocks(folder, slot, game):
        name, head, body = b.identity
        if not name or head is None or body is None:
            continue
        if voided and additions.is_removable_backfill(b) and b.identity in voided:
            continue
        p = reg.get(name, head, body)
        if b.heading.startswith(("Death", "Disappeared")):
            p = _namesake_for(reg, p, b)     # a living villager's dead namesake (the identity audit)
        sex = b.value("Sex")
        if sex in ("Male", "Female") and p.sex is None:
            p.sex = sex
        # Every status any record gives them, held then or now (a former Tribal Chief stays one).
        for title in _values(b.value("Special villager")):
            _add_status(p, status_marks(title))
        _add_status(p, _values(b.value("Custom title")))
        if (b.value("How") or "").strip() == CONVERTED_HOW:
            p.converted = True
        # A Heathen then (New Believers): the snapshot's Faction, an Island Events "Heathen: no -> yes", a
        # "Left the tribe: became a Heathen" record.  A status ever held, as every other (_finish_statuses).
        if (b.value("Faction") or "").strip() == "Heathen" \
                or "yes" in [v.lower() for v in _values(b.value("Heathen"))] \
                or (b.value("What happened") or "").strip() == LEFT_FOR_THE_HEATHENS:
            _add_status(p, ["Heathen"])
        if (b.value("What happened") or "").strip() == LEFT_FOR_THE_HEATHENS:
            p.left_heathen = True
        if b.heading.startswith("Villager "):
            faction = (b.value("Faction") or "").strip() or additions._faction_of_title(b.value("Special villager"))
            when = "9999" if additions.is_population(b.path) else (b.date or "")
            if faction in ("Heathen", "Believer") and (p.faction_seen is None or when >= p.faction_seen[0]):
                p.faction_seen = (when, faction)
        else:
            # Any other record (a Death, a Disappeared, an Island Events change) whose title -- the one held
            # after it, the last of an "old -> new" -- is a Heathen role (Heathen Doctor, Heathen Mommy, ...)
            # says they were a Heathen then: only a current Heathen holds one (_faction_of_title).  A later
            # snapshot still decides; a conversion still keeps them (is_unconverted_heathen).
            titles = _values(b.value("Special villager"))
            when = b.date or ""
            if titles and additions._faction_of_title(titles[-1]) == "Heathen" \
                    and (p.faction_seen is None or when >= p.faction_seen[0]):
                p.faction_seen = (when, "Heathen")
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
        elif b.heading.startswith("Arrived") and is_backfilled_arrival(b) and p.birth_record is not None:
            # A Birth wins over a backfilled "How: unknown" Arrived record: the backfill wrote it when
            # it could not see the Birth (the owner's Cheop Bahati, born "Cheop" before Last Names).
            pass
        elif b.heading.startswith("Arrived"):
            p.arrived = True
            # A backfilled "How: unknown" never replaces how a real Arrived record says they came.
            if not (is_backfilled_arrival(b) and p.how):
                p.how = b.value("How") or p.how
            seen = re.search(r"first seen (\d{4}-\d{2}-\d{2} \d{2}:\d{2})", b.value("Age at arrival") or "")
            if seen and (p.first_seen is None or seen.group(1) < p.first_seen[:16]):
                p.first_seen = seen.group(1)
        if b.date and b.heading.startswith("Villager ") and not additions.is_population(b.path):
            if p.key in reg.living_dups:            # two of this name and look listed in one snapshot
                seen_twice = listed.setdefault((b.date, p.key), 0) + 1
                listed[(b.date, p.key)] = seen_twice
                if seen_twice == 2 and (p.key not in reg.dup_seen or b.date < reg.dup_seen[p.key]):
                    reg.dup_seen[p.key] = b.date
            reg.snapshots.setdefault(b.date, set()).add(p.id)
            if p.first_seen is None or b.date < p.first_seen:
                p.first_seen = b.date
        if "running" in [w.strip().lower() for w in (b.value("Likes") or "").split(",")]:
            reg.ran.add(p.id)
        if not p.alive and p.likes is None and b.value("Likes") is not None and b.value("Dislikes") is not None \
                and "->" not in (b.value("Likes") + b.value("Dislikes")):
            # The dead (and the gone) by their logs' words; the living keep their save's.
            p.likes, p.dislikes = ([w.strip() for w in (b.value(label) or "").split(",")
                                    if w.strip() and w.strip() != "(none)"] for label in ("Likes", "Dislikes"))
        seen_likes = _like_words(b.value("Likes"))
        if seen_likes is None and b.heading.startswith("Villager "):
            seen_likes = frozenset()         # a snapshot leaves the line out for a villager who likes nothing
        if seen_likes is not None:
            p.likes_seen.add(seen_likes)
        age = b.value("Age")
        if age and age.lstrip("-").isdigit() and not p.alive and p.gone != "died":
            p.age = max(p.age or 0, int(age))
        parents = _snapshot_parents(b.lines)
        for label, sex, attr in (("Father", "Male", "father"), ("Mother", "Female", "mother")):
            if label in parents and getattr(p, attr) is None:
                parent = reg.get(*parents[label])
                parent.sex = parent.sex or sex
                setattr(p, attr, parent.id)


def _file_statuses(reg: _Registry, folder: Path, game: int, slot: int) -> None:
    """The statuses the save's graves and the patcher's own files keep, after every villager is known
    and joined (their looks, names and records): each only on the one villager it can be."""
    import struct
    import vv_last_names as ln
    try:
        data = ln.save_path(folder, game, slot).read_bytes()
    except OSError:
        return
    people = list(reg.people.values())
    # The graves: The Secret City's Tribal Chief byte, and the later three games' Esteemed Elder byte
    # (vv_graves._title_of), on the one villager recorded dead at that age by that name (and looks).
    try:
        import vv_graves
        cap = vv_graves.LAYOUTS[game].name_cap
        graves = vv_graves.read_graves(game, data)
    except Exception:                   # the graves are one source of several: never the tree's undoing
        graves = []
    for g in graves:
        title = g.values.get("title")
        master = (g.values.get("grave") or "").startswith("Master ")    # the grave's best skill, mastered
        if not title and not master:
            continue
        looks = (g.values.get("head"), g.values.get("body"))
        fits = [p for p in people if p.gone == "died" and not p.alive and p.age == g.age
                and (g.name in (p.name, *p.former) or (len(g.name) >= cap - 1 and p.name.startswith(g.name)))
                and (looks[0] is None or looks == (p.head, p.body) or looks in p.old_looks)]
        if len(fits) == 1:
            _add_status(fits[0], status_marks(title))
            job = g.values["grave"][len("Master "):] if master else ""
            if job and job not in fits[0].masters:
                fits[0].masters.append(job)
    try:
        entries = ln._entries(game, data)
    except Exception:
        return
    f = ln.FIELDS[game]

    def holder(at: int) -> Person | None:
        key = reg.current((_cstr(data, at, f.name_cap), _i32(data, at + f.head), _i32(data, at + f.body)))
        return reg.people.get(reg.by_key.get(key, -1))
    # New Believers' Former Heathens file: a converted Heathen's mask (or Chief), by their title identity.
    if game == 5:
        try:
            import vv_lost_titles as lt
            import vv_save_layout as layout
            rows = lt._read_file(layout.route(folder, lt.FORMER_FILE.format(slot=slot)), lt.FORMER_MAGIC,
                                 lt.FORMER_VERSION, game, lt.FORMER_HEADER, lt.FORMER_ENTRY, 1024) or []
            kinds: dict[int, set] = {}
            for row in rows:
                identity, kind = struct.unpack("<II", row)
                kinds.setdefault(identity, set()).add(kind)
            ids = {at: ln._title_identity(data, at, f) for at in entries}
            for at, identity in ids.items():
                one = kinds.get(identity, set())
                p = holder(at)
                if p is not None and len(one) == 1 and list(ids.values()).count(identity) == 1:
                    _add_status(p, status_marks(FORMER_FILE_TITLES.get(next(iter(one)))))
        except Exception:
            pass
    # The Custom Titles file: each living villager's own title, as the game's load gives it.
    try:
        import vv_villager_info
        held = vv_villager_info.file_titles(folder, game, slot) or {}
    except Exception:
        held = {}
    for key, title in held.items():
        p = reg.people.get(reg.by_key.get(reg.current(key), -1))
        if p is not None:
            _add_status(p, _values(title))


def _finish_statuses(reg: _Registry) -> None:
    """A villager the records say converted from the Heathens, with no mask colour known, is a Former
    Heathen; anyone who is or ever was a Heathen -- the save's faction, a Heathen role, a conversion, a
    former Heathen's title -- has the Heathen status too (the owner, 2026-10-22: an ordinary Heathen is
    marked "Heathen", and one who converts keeps it as a status ever held, beside their Converted or Former
    mark); every list in the games' order."""
    converted = ("Retired Heathen Chief", "Former Heathen Master")
    for p in reg.people.values():
        if p.converted and not any(s in converted or s.startswith("Converted ") for s in p.statuses):
            _add_status(p, ["Former Heathen"])
        if p.heathen or p.converted or any(s.startswith(("Heathen ", "Former Heathen", "Converted "))
                                           or s == "Retired Heathen Chief" for s in p.statuses):
            _add_status(p, ["Heathen"])
        p.statuses = _sorted_statuses(p.statuses)


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
        if rec.kind == "lost" and rec.mother is not None and rec.mother.name:
            # Her babies were lost with her (she died or disappeared carrying or nursing them): the
            # Conception is closed, and no baby of it is ever on the way (the owner, 2026-10-09).
            mother = reg.current((rec.mother.name, rec.mother.head, rec.mother.body))
            reg.conceptions.pop(mother, None)
            reg.lost.append((mother, rec.babies or 1))
        if rec.kind != "birth" or rec.child is None or not rec.child.name:
            last = None
            continue
        reg.conceptions.pop(reg.current((rec.mother.name, rec.mother.head, rec.mother.body)) if rec.mother else None,
                            None)
        child = reg.get(rec.child.name, rec.child.head, rec.child.body)
        if child.birth_record is not None:
            # A second Birth record of this name and look is another villager (a Birth is written once
            # per child): never the first one's (the identity audit; _namesakes_by_birth decides who
            # of them the living villager is).
            key = (child.name, child.head, child.body)
            pid = max(reg.people, default=0) + 1
            reg.people[pid] = Person(pid, *key)
            reg.namesakes.setdefault(key, [child.id]).append(pid)
            child = reg.people[pid]
        child.birth_record = index
        ids = []
        for person, attr, sex in ((rec.father, "father", "Male"), (rec.mother, "mother", "Female")):
            parent_id = None
            if person is not None and person.name:
                parent = reg.get(person.name, person.head, person.body)
                parent.sex = parent.sex or sex
                parent_id = parent.id
                if getattr(child, attr) is None:
                    setattr(child, attr, parent.id)
            ids.append(parent_id)
        reg.birth_of[child.id] = (index, ids[0], ids[1])
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


def _namesakes_by_birth(reg: _Registry, notes: list[str]) -> None:
    """Who of the villagers born with one name and look the living one is (the identity audit): the
    one whose Birth names the parents the save keeps on her record (The Lost Children on) -- never the
    name and look alone.  The registry's own person for the key is the living one (the save is read
    first); she takes that Birth and its litter, and the Birth she was given in log order goes to the
    namesake instead, with its own parents.  When no Birth -- or more than one -- names her record's
    parents (A New Home keeps none on the record), no Birth is hers: the one she was given becomes a
    villager of its own, her record keeps its own parents, and the notes say so."""
    for key, pids in reg.namesakes.items():
        living = reg.people[pids[0]]
        if not living.alive or living.id not in reg.birth_of:
            continue
        mine = reg.save_parents.get(living.id)
        matches = [pid for pid in pids if mine and None not in mine
                   and reg.birth_of.get(pid, (None, None, None))[1:] == mine]
        given = reg.birth_of[living.id]
        if len(matches) == 1 and matches[0] == living.id:
            continue                                   # the Birth she was given is hers
        if len(matches) == 1:
            other = reg.people[matches[0]]
            # Swap the Births: hers to her, the one she was given to the namesake, with its parents.
            living.birth_record, other.birth_record = other.birth_record, living.birth_record
            living.litter, other.litter = other.litter, living.litter
            reg.birth_of[living.id], reg.birth_of[other.id] = reg.birth_of[other.id], given
            other.father, other.mother = given[1], given[2]
            continue
        # Not told apart: one of the Births is hers and the rest are the namesakes', but which is not
        # known -- so no Birth (and no Birth's parents) is given to any of them; she keeps her record's
        # own parents, and the namesakes keep none.
        for pid in pids:
            person = reg.people[pid]
            person.birth_record, person.litter = None, None
            person.father, person.mother = (mine if mine else (None, None)) if pid == living.id else (None, None)
            reg.birth_of.pop(pid, None)
        notes.append(f"{key[0]} (head {key[1]}, body {key[2]}): {len(pids)} Birth records name a child with this name "
                     "and look; which of them is the living villager's could not be told (her record's parents "
                     "name none of them, or more than one), so no Birth record or parents are given to any of them.")


def _namesake_for(reg: _Registry, p: Person, b) -> Person:
    """The villager a Death or Disappeared record of `p`'s name and look is about: `p`, or -- `p`
    alive -- the one namesake born with that look who is not alive and has no such record yet."""
    if not p.alive:
        return p
    others = [reg.people[q] for q in reg.namesakes.get((p.name, p.head, p.body), [])
              if not reg.people[q].alive and not reg.people[q].gone]
    return others[0] if len(others) == 1 else p


def _living_namesake_births(reg: _Registry) -> None:
    """LIVING NAMESAKES' BIRTHS (the owner, v1.35.85): two living villagers of one name, head and body each take
    the Birth record naming the parents their own save record keeps (The Lost Children on) -- exactly one Birth
    for exactly one of them, never on a guess.  Births no living one is told by are theirs, which is not known,
    while there are no more of them than living namesakes without a Birth; beyond that, each is a villager of its
    own (born, then gone), with that Birth's parents.  Before _namesakes_by_birth, which then has nothing left of
    the key."""
    for key, living in reg.living_dups.items():
        living = [pid for pid in living if pid in reg.people]
        pids = list(dict.fromkeys(reg.namesakes.get(key, [living[0]])))
        records = [(pid, reg.people[pid].birth_record, reg.people[pid].litter, reg.birth_of[pid])
                   for pid in pids if pid in reg.birth_of]
        reg.namesakes.pop(key, None)
        if not records:
            continue
        for pid, *_rest in records:
            reg.people[pid].birth_record = reg.people[pid].litter = None
            reg.birth_of.pop(pid, None)
        claims: dict[int, list] = {}
        for rec in records:
            fits = [q for q in living if reg.save_parents.get(q) and None not in reg.save_parents[q]
                    and rec[3][1:] == reg.save_parents[q]]
            if len(fits) == 1:
                claims.setdefault(fits[0], []).append(rec)
        left = []
        for rec in records:
            owner = next((q for q, recs in claims.items() if rec in recs and len(recs) == 1), None)
            if owner is None:
                left.append(rec)
                continue
            p = reg.people[owner]
            p.birth_record, p.litter = rec[1], rec[2]
            reg.birth_of[owner] = rec[3]
        spare = [pid for pid in pids if pid not in living]     # the Births' own villagers _births made
        untold = [q for q in living if reg.people[q].birth_record is None]
        if len(left) <= len(untold):
            # No more Births left than living namesakes not told by one (twins still alive, a record keeping no
            # parents): each Birth is one of theirs, which one is not known -- so none is given, and none is a
            # villager of its own (no namesake who never lived).
            left = []
        for rec in left:
            pid = spare.pop(0) if spare else max(reg.people, default=0) + 1
            p = reg.people.setdefault(pid, Person(pid, *key))
            p.birth_record, p.litter = rec[1], rec[2]
            p.father, p.mother = rec[3][1], rec[3][2]
            reg.birth_of[pid] = rec[3]
        for pid in spare:                                       # a Birth a living one took: not a villager
            if not any(pid in (r.father, r.mother) for r in reg.people.values()):
                del reg.people[pid]


# The game's own age for having a child: 18 villager years at conception, 360 age units (the partner search
# 0x45CE00 and the picker's adult class 0x45D460 take 18 to 49: vv_game_mechanics_catchup).  A parent is at least
# that old when the child is born.  Only that bound rules anyone out: the upper one (49) is not used, because
# the owner's saves hold fathers older than it at the birth (The Secret City's 256 copy: Tepeu Tamikai, 71 at
# Sakou Makawee's birth) -- a wider window only asks more often, it never links wrongly.
ADULT_UNITS = YOUNGEST_YEARS * UNITS_PER_YEAR


def could_be_parent(parent: Person, child: Person) -> bool:
    """Whether a LIVING villager was old enough to be `child`'s parent by the game's age: the child's age now and
    the parent's give the parent's age at the birth; a child gone (no age now) or on the way asks only that the
    parent is, or was, of age."""
    if parent.age is None:
        return True
    if child.alive and not child.upcoming and child.age is not None:
        return parent.age - child.age >= ADULT_UNITS
    return parent.age >= ADULT_UNITS


@dataclass
class ParentQuestion:
    """A child whose record names a parent by a name and look two (or more) living villagers have, each old
    enough to be that parent: which one?  `choices` are the living namesakes, oldest first (their ids); the
    answer is kept as "The oldest", "The second oldest"... in Answered questions (vv_answered_questions.
    keep_parent), which stays true as they age together."""
    child: Key
    parent: Key
    label: str                  # "Father" or "Mother"
    choices: list
    texts: list                 # each choice in words: "The oldest (1583 game units, 79 years old; parents ...)"
    child_id: int = 0
    # The child's own place by age among living namesakes of theirs (1 the oldest; 0 when the child has none):
    # two children of one name and look are two questions, each kept under its own answer (Codex, PR #653).
    child_rank: int = 0
    child_age: str = ""

    @property
    def who(self) -> str:
        """The child in words; a child with a living namesake is told apart by their place by age and age."""
        if not self.child_rank:
            return self.child[0]
        return f"{self.child[0]} ({rank_word(self.child_rank - 1).lower()} of that name, {self.child_age})"

    @property
    def text(self) -> str:
        return (f"{self.who}'s {self.label.lower()} is {self.parent[0]} (head {self.parent[1]}, body "
                f"{self.parent[2]}), and {len(self.choices)} living villagers have that name and look, each old "
                "enough to be the parent. Which one?")


RANK_WORDS = ("The oldest", "The second oldest", "The third oldest", "The fourth oldest", "The fifth oldest")


def rank_word(k: int) -> str:
    return RANK_WORDS[k] if k < len(RANK_WORDS) else f"Number {k + 1} by age"


def _parents_by_age(reg: _Registry, answers: dict, notes: list[str]) -> list[ParentQuestion]:
    """LINK BY AGE (the owner, v1.35.85): every record names a parent only by name, head and body, which two
    living namesakes share.  A child is linked to the one who was old enough to be their parent at the child's
    birth (could_be_parent); when more than one could be, to the one the player chose (`answers`: (child key,
    parent key, "Father"/"Mother") -> a RANK_WORDS answer); otherwise to neither -- never a guess -- and the
    question is returned for the Family Tree Maker to ask.  A child who has a living namesake is told apart by
    their own place by age (`answers` keys end in that rank; 0 for a child with none, which is also what an
    answer kept before the rank was is read as -- so an old answer is never given to one of two namesakes)."""
    questions: list[ParentQuestion] = []
    groups: dict = {}
    for key, ids in reg.living_dups.items():
        group = sorted((pid for pid in ids if pid in reg.people and reg.people[pid].alive),
                       key=lambda pid: (-(reg.people[pid].age or 0), ids.index(pid)))
        if len(group) < 2:
            continue
        for rank, pid in enumerate(group, 1):
            reg.people[pid].namesake_rank = rank
        groups[key] = group
    for key, group in groups.items():
        first = reg.by_key.get(key, group[0])
        if reg.people[first].first_seen and key in reg.dup_seen:
            for pid in group:
                if reg.people[pid].first_seen is None:
                    reg.people[pid].first_seen = reg.dup_seen[key]
        for child in list(reg.people.values()):
            # A namesake can be the child of another namesake (a Tepeu fathered by an older Tepeu): never their
            # own parent, so the others are the candidates (Codex, PR #653).
            pool = [pid for pid in group if pid != child.id]
            for attr, label in (("father", "Father"), ("mother", "Mother")):
                if getattr(child, attr) not in group:
                    continue
                fits = [pid for pid in pool if could_be_parent(reg.people[pid], child)]
                child_key = (child.key if not child.upcoming else
                             (f"Upcoming child of {reg.people[child.mother].name}",) + reg.people[child.mother].key[1:]
                             if child.mother in reg.people else child.key)
                child_rank = 0 if child.upcoming else child.namesake_rank
                said = answers.get((child_key, key, label, child_rank))
                chosen = None
                if said in RANK_WORDS[:len(group)] or (said or "").startswith("Number "):
                    k = RANK_WORDS.index(said) if said in RANK_WORDS else int(said.split()[1]) - 1
                    chosen = group[k] if k < len(group) and group[k] != child.id else None
                elif len(fits) == 1:
                    chosen = fits[0]
                setattr(child, attr, chosen)
                if chosen is None:              # two or more could be (or none by the ages): the player says
                    who = fits or pool
                    questions.append(ParentQuestion(
                        child_key, key, label, who,
                        [f"{rank_word(group.index(pid))} ({reg.people[pid].age_text()})" for pid in who], child.id,
                        child_rank, child.age_text() if child_rank else ""))
    return questions


def _saved_rename_answers(folder: Path, game: int, slot: int) -> dict:
    """The renamed-villager answers the Family Tree Maker's saved edits keep; none when there is no
    readable file (a damaged file is the tree's to report, not this loader's)."""
    import vv_family_tree as ft
    try:
        path = ft.Edits.path(folder, game, slot)
        return dict(ft.Edits.load(path).renames) if path.is_file() else {}
    except (OSError, ValueError):
        return {}


def _identity_answers(folder: Path, game: int, slot: int) -> dict:
    """The player's answers to "the same villager?": the Family Tree Maker's (Answered questions) and the
    reconciliation's "looks" questions answered "Keep as is (the same villager; the looks changed)"
    (src/vv_reconcile.py) -- {(older key, newer key): vv_answered_questions.SAME or DIFFERENT}."""
    import ast
    import vv_answered_questions as aq
    out: dict = {}
    try:
        import vv_log_additions as additions
        import vv_reconcile as reconcile
        for field_, answer in reconcile.answered(folder, game, slot,
                                                 additions.current_villages(folder, game, slot)).items():
            parts = field_.split("|")
            if len(parts) != 3 or parts[0] != "looks" or not answer.startswith(reconcile.KEEP):
                continue
            try:
                old, new = ast.literal_eval(parts[1]), ast.literal_eval(parts[2])
            except (ValueError, SyntaxError):
                continue
            if isinstance(old, tuple) and isinstance(new, tuple) and len(old) == len(new) == 3:
                out[(old, new)] = aq.SAME
    except (OSError, ValueError):
        pass
    out.update(aq.identity_answers(folder, game, slot))      # the tree's own answer wins
    return out


def load_village(folder: Path, game: int, slot: int, full_names: bool = True,
                 rename_answers: dict | None = None, identity_answers: dict | None = None) -> Village:
    """The slot's village, its living villagers and every relative the save and logs know.

    With `full_names` (the Family Tree Maker and the Village Matchmaker), a living villager whose name
    the Villager Details screen cut is the same villager as the logs' record of their full name, and
    is shown by it (the owner, 2026-10-07: "Family trees will use the full names from the logs, then
    the save data").  Without (Last Names, Number Duplicate Names: they rename the save and the logs,
    so they work from the names as written), everyone keeps the name the records carry.

    `rename_answers` (Edits.renames) are the player's answers to the renamed-villager questions: see
    _renamed_villagers.  Without an answer a question is only asked (Village.rename_questions)."""
    import vv_log_additions as additions
    import vv_tribe_rename
    folder = Path(folder)
    if rename_answers is None:
        # Every caller sees the same people: a renamed villager the player kept (Edits.renames "current")
        # is one person, whichever window or dialog loads the village.
        rename_answers = _saved_rename_answers(folder, game, slot)
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
    _living_namesake_births(reg)
    _namesakes_by_birth(reg, notes)
    _log_people(reg, folder, game, slot)
    if game == 1:
        _vv1_from_sidecar(reg, folder, slot)
    for pid in reg.ran:                 # the dead and gone: as their logs say (the living: their save)
        if not reg.people[pid].alive:
            reg.people[pid].runner = True
    _logged_renames(reg, folder, game, slot)
    _answered_renames(reg, folder, game, slot, rename_answers or {}, notes)
    if identity_answers is None:
        identity_answers = _identity_answers(folder, game, slot)
    identity_questions = _unrecorded_looks(reg, identity_answers)
    checker = tools.load_checker()
    exact, by_name = checker.known_sexes(folder, game)
    for p in reg.people.values():
        if p.sex is None:
            p.sex, _source = checker.sex_for(game, {"name": p.name, "head": p.head, "body": p.body},
                                             exact, by_name)
    questions = _renamed_villagers(reg, rename_answers or {}, notes)
    import vv_last_names as ln
    tribe = ""
    try:
        games = {g.number: g for g in vv_tribe_rename.GAMES}
        tribe = vv_tribe_rename.save_name(games[game], ln.save_path(folder, game, slot).read_bytes()) or ""
    except (OSError, KeyError, ValueError):
        pass
    _upcoming(reg)
    import vv_answered_questions as aq
    parent_questions = _parents_by_age(reg, aq.parent_answers(folder, game, slot) if reg.living_dups else {}, notes)
    for (name, _head, _body), babies in reg.lost:
        notes.append(f"{name} lost {'a baby' if babies == 1 else f'{babies} babies'} before birth: she died or "
                     "disappeared while carrying or nursing, and "
                     f"{'it was' if babies == 1 else 'they were'} never born.")
    village = Village(game, slot, tribe, reg.people, notes, sorted(reg.snapshots))
    village.rename_questions = questions
    village.parent_questions = parent_questions
    village.identity_questions = [q for q in identity_questions
                                  if q.older in reg.by_key and q.newer in reg.by_key
                                  and reg.by_key[q.older] != reg.by_key[q.newer]]
    village.relooked = {old: reg.current(old) for old in reg.relooked if reg.current(old) != old}
    village.full_names = {cut: full[0] for cut, full in reg.full.items()}
    for old, now in village.relooked.items():
        if now in reg.by_key:
            reg.people[reg.by_key[now]].old_looks.append((old[1], old[2]))
    _file_statuses(reg, folder, game, slot)
    _finish_statuses(reg)
    for p in reg.people.values():
        p.placeholder = is_placeholder_father(game, p)
    _generations(village, reg.snapshots)
    number_people(village)
    if additions.current_villages(folder, game, slot) is None:
        notes.append("The save's tribe name could not be read, so records of every village this "
                     "slot has held were read.")
    return village


def _renamed_villagers(reg: _Registry, answers: dict, notes: list[str]) -> list[RenameQuestion]:
    """A logged villager no living villager is called, recorded neither dead nor gone, with the sex, head,
    body and likes of exactly one living villager who is no younger than the record, is probably that
    villager after the player renamed them (the owner, 2026-10-13: Lupa Tangaroa is now Coral Tangaroa).
    Never decided by the name, and never when two records or two villagers fit: those are listed in the
    notes and left apart.  The player is asked "Keep <current> or <old>?"; answered "current" the two are
    ONE person under the current name with the old name in `former`; answered "old" they stay apart (the
    tree as it always showed them); unanswered, nothing changes and the question is returned."""
    together: dict[int, set[int]] = {}
    for ids in reg.snapshots.values():
        for pid in ids:
            together.setdefault(pid, set()).update(ids)
    living = [q for q in reg.people.values() if q.alive and not q.upcoming]
    living_names = {q.name for q in living}
    pairs: list[tuple[Person, Person]] = []
    for o in list(reg.people.values()):
        if o.alive or o.gone or o.upcoming or o.placeholder or o.head is None or o.body is None \
                or o.sex is None or not o.likes_seen or o.name in living_names:
            continue
        fits = [q for q in living
                if q.name != o.name and q.sex == o.sex and q.head == o.head and q.body == o.body
                and q.likes is not None and frozenset(w.lower() for w in q.likes) in o.likes_seen
                and (o.age is None or q.age is None or q.age >= o.age)
                and not (o.birth_record is not None and q.birth_record is not None)
                and q.id not in together.get(o.id, ())]
        if len(fits) == 1:
            pairs.append((o, fits[0]))
        elif len(fits) > 1:
            notes.append(f"{o.name} (head {o.head}, body {o.body}) is in the logs but not in the save; "
                         f"{', '.join(q.name for q in fits)} all have the same sex, looks and likes, so "
                         "they were not joined.")
    questions: list[RenameQuestion] = []
    for o, q in pairs:
        rivals = [x.name for x, y in pairs if y.id == q.id]
        if len(rivals) > 1:
            notes.append(f"{q.name} could be {' or '.join(rivals)} (the same sex, looks and likes), so they "
                         "were not joined.")
            continue
        ask = RenameQuestion(o.name, q.name, o.head, o.body, o.id, q.id)
        if answers.get(ask.key) == "current":
            _merge_renamed(reg, o, q)
        elif answers.get(ask.key) != "old":
            questions.append(ask)
    return questions


def _merge_renamed(reg: _Registry, p: Person, q: Person) -> None:
    """The logged record `p` is the living villager `q` under an older name: `q` keeps every fact the
    records give either and notes the old name."""
    for attr in ("father", "mother", "birth_record", "litter", "sex"):
        if getattr(q, attr) is None:
            setattr(q, attr, getattr(p, attr))
    if p.first_seen and (q.first_seen is None or p.first_seen < q.first_seen):
        q.first_seen = p.first_seen
    q.arrived = q.arrived or p.arrived
    # A renamed founder is still a founder: the newer record's "unknown" is not a way in.
    q.how = "Founder" if p.how == "Founder" and q.how in (None, "", "unknown") else (q.how or p.how)
    q.runner = q.runner or p.runner
    q.likes_seen |= p.likes_seen
    _add_status(q, p.statuses)          # a status held under the old name is still theirs
    _merge_faction(p, q)
    q.former = [p.name] + [n for n in q.former if n != p.name] + [n for n in p.former if n not in q.former]
    for r in reg.people.values():
        if r.father == p.id:
            r.father = q.id
        if r.mother == p.id:
            r.mother = q.id
    for ids in reg.snapshots.values():
        if p.id in ids:
            ids.discard(p.id)
            ids.add(q.id)
    reg.ran.discard(p.id)
    del reg.people[p.id]
    reg.by_key[p.key] = q.id


def _likes_fit(p: Person, q: Person) -> bool | None:
    """Whether q's likes are one of the lists the records give p, give or take a like gained or lost in
    between (the patcher's running grant adds one); None when either side does not say."""
    if not p.likes_seen or q.likes is None:
        return None
    mine = frozenset(w.lower() for w in q.likes)
    return any(mine == seen or mine <= seen or seen <= mine for seen in p.likes_seen)


def _same_name(older: str, newer: str) -> bool:
    """The same name -- or the newer one is the older with a number Number Duplicate Names (or VVFP Number
    Names.dll) added since ("Mama Peponi" -> "Mama Peponi II"): a record of the older look keeps the name it
    had, because numbering renames each villager by their name AND looks."""
    return older == newer or (older == unnumbered(older) and unnumbered(newer) == older)


def _could_be_same(reg: _Registry, p: Person, q: Person, together: dict, seen_on: dict) -> bool:
    """Whether nothing proves the older record `p` and the villager `q` two villagers: the same name; never
    listed together in one History snapshot; the sex, the parents named on both and the age fit (p never
    older than q -- now, or at death); not both with a Birth record of their own; p's History snapshots
    all before q's; and q older than every living child the records give p."""
    if q.id == p.id or q.upcoming or q.placeholder or not _same_name(p.name, q.name) or not (q.alive or q.gone):
        return False
    if p.sex is not None and q.sex is not None and p.sex != q.sex:
        return False
    if q.id in together.get(p.id, ()):
        return False
    if p.birth_record is not None and q.birth_record is not None:
        return False
    if not all(a is None or b is None or a == b for a, b in ((p.father, q.father), (p.mother, q.mother))):
        return False
    if p.age is not None and q.age is not None and p.age > q.age:
        return False
    mine, theirs = seen_on.get(p.id, []), seen_on.get(q.id, [])
    if mine and theirs and max(mine) >= min(theirs):
        return False
    if q.alive and q.age is not None:
        for c in reg.people.values():
            if p.id in (c.father, c.mother) and c.alive and c.age is not None and c.age >= q.age:
                return False
    return True


def _certain(reg: _Registry, p: Person, q: Person, seen_on: dict, dates: list[str]) -> str | None:
    """What ties the older record `p` to the villager `q` beyond doubt, in words, or None:
    * a parent named on both (the same mother or father: the games' name pools repeat a first name, a
      family does not);
    * an unbroken History: p is in every snapshot up to one, and q from the very next one on, the age only
      moving on and the likes the same."""
    if any(a is not None and a == b for a, b in ((p.father, q.father), (p.mother, q.mother))):
        return "the same parents"
    mine, theirs = seen_on.get(p.id, []), seen_on.get(q.id, [])
    if mine and theirs and _likes_fit(p, q) is not False:
        last, first = max(mine), min(theirs)
        if last in dates and first in dates and dates.index(first) == dates.index(last) + 1:
            return f"in the Village History up to {last[:16]} and from {first[:16]} on, never both"
    return None


def _person_text(reg: _Registry, p: Person, seen_on: dict) -> str:
    bits = [f"head {p.head}, body {p.body}", p.sex or "sex unknown"]
    if p.age is not None:
        bits.append(f"{'died at ' if p.gone == 'died' else ''}{p.age} game units")
    bits.append("in the save now" if p.alive else {"died": "dead", "disappeared": "disappeared",
                                                   "left": "left"}.get(p.gone, "in older records only"))
    dates = seen_on.get(p.id, [])
    if dates:
        bits.append(f"in the Village History {dates[0][:16]}" + (f" to {dates[-1][:16]}" if len(dates) > 1 else ""))
    parents = [f"{w} {reg.people[x].name}" for w, x in (("father", p.father), ("mother", p.mother))
               if x is not None and x in reg.people]
    if parents:
        bits.append(", ".join(parents))
    if p.birth_record is not None:
        bits.append("has a Birth record")
    elif p.arrived:
        bits.append(f"arrived ({p.how})" if p.how else "has an Arrived record")
    return "; ".join(bits)


def _move_state(reg: _Registry, p: Person, q: Person) -> None:
    """Everything the registry keeps under the older record `p` -- by its key or its id -- now `q`'s (Codex,
    #602: an expecting mother whose looks changed lost her Conception, so her baby on the way lost its father
    and the babies she carries)."""
    if p.key in reg.conceptions and q.key not in reg.conceptions:
        reg.conceptions[q.key] = reg.conceptions[p.key]
    reg.conceptions.pop(p.key, None)
    reg.lost = [(q.key if mother == p.key else mother, babies) for mother, babies in reg.lost]
    for table in (reg.expected, reg.due, reg.birth_of, reg.save_parents):
        if p.id in table and q.id not in table:
            table[q.id] = table[p.id]
        table.pop(p.id, None)
    for key, pids in reg.namesakes.items():
        reg.namesakes[key] = list(dict.fromkeys(q.id if pid == p.id else pid for pid in pids))
    reg.birth_of = {pid: ((index, q.id if f == p.id else f, q.id if m == p.id else m))
                    for pid, (index, f, m) in reg.birth_of.items()}
    reg.save_parents = {pid: tuple(q.id if x == p.id else x for x in parents)
                        for pid, parents in reg.save_parents.items()}


def _merge_into(reg: _Registry, p: Person, q: Person) -> None:
    """The older record `p` is the villager `q` before their looks (or title) changed: one villager, `q`,
    who keeps every fact the records give either; p's look is remembered as one of q's (relooked)."""
    for attr in ("father", "mother", "birth_record", "litter", "sex"):
        if getattr(q, attr) is None:
            setattr(q, attr, getattr(p, attr))
    if p.first_seen and (q.first_seen is None or p.first_seen < q.first_seen):
        q.first_seen = p.first_seen
    q.arrived = q.arrived or p.arrived
    q.how = "Founder" if p.how == "Founder" and q.how in (None, "", "unknown") else (q.how or p.how)
    q.runner = q.runner or p.runner
    q.likes_seen |= p.likes_seen
    _add_status(q, p.statuses)          # a change of looks or title never takes a status away
    _merge_faction(p, q)
    for r in reg.people.values():
        if r.father == p.id:
            r.father = q.id
        if r.mother == p.id:
            r.mother = q.id
    for ids in reg.snapshots.values():
        if p.id in ids:
            ids.discard(p.id)
            ids.add(q.id)
    if p.id in reg.ran:
        reg.ran.discard(p.id)
        reg.ran.add(q.id)
    _move_state(reg, p, q)
    del reg.people[p.id]
    reg.by_key[p.key] = q.id
    reg.relooked[p.key] = q.key


def _unrecorded_looks(reg: _Registry, answers: dict | None = None) -> list[IdentityQuestion]:
    """IDENTITY SURVIVES ANY CHANGE OF LOOKS OR TITLE (the owner, v1.35.80 update, all five games: "A change in
    body, head and mask does not mean they disappeared.  A change in title or special villager status does
    not mean they disappeared.").  A record of a villager with looks no villager has now, who is not recorded
    dead or gone (the tree would say "left the village"), is the villager of that name whose stable facts fit
    -- the sex, the parents, the age only moving on, the likes, never listed together -- and the looks only
    break ties, never split one villager into two.  The Secret City's Tribal Chief is given the chief's robe
    (a new body) by the game itself with no record of it: the owner's chiefs were shown "left the village"
    and again under a numeral.  Earlier (2026-10-08): Papu Tamikai, born with his twin Paco's head 16 and now
    head 5, after an island event.

    Joined when exactly one villager fits and something ties them beyond doubt (_certain: the same parents,
    or an unbroken History), or the player said they are the same (`answers`: the Family Tree Maker's
    question, or the reconciliation's "looks" question answered "the same villager").  "Different" keeps
    them apart.  Anything else that fits is returned as an IdentityQuestion for the Family Tree Maker to ask;
    nothing is joined on a guess."""
    import vv_answered_questions as aq
    answers = answers or {}
    dates = sorted(reg.snapshots)

    def views():
        together: dict[int, set[int]] = {}
        seen_on: dict[int, list[str]] = {}
        for date in dates:
            ids = reg.snapshots[date]
            for pid in ids:
                together.setdefault(pid, set()).update(ids)
                seen_on.setdefault(pid, []).append(date)
        return together, seen_on

    def said(p: Person, q: Person) -> str | None:
        return aq.identity_said(answers, p.key, q.key)

    def older_records() -> list[Person]:
        return [p for p in reg.people.values()
                if not (p.alive or p.gone or p.upcoming or p.head is None or p.body is None or p.key in reg.bodies)]

    changed = True
    while changed:
        changed = False
        together, seen_on = views()
        by_name: dict[str, list[Person]] = {}
        for q in reg.people.values():
            by_name.setdefault(unnumbered(q.name), []).append(q)
        for p in older_records():
            fits = [q for q in by_name.get(unnumbered(p.name), []) if _could_be_same(reg, p, q, together, seen_on)
                    and said(p, q) != aq.DIFFERENT]
            same = [q for q in fits if said(p, q) == aq.SAME]
            if len(same) == 1:
                target = same[0]
            elif len(fits) == 1 and _certain(reg, p, fits[0], seen_on, dates):
                target = fits[0]
                # ...and no other older record is tied to them the same way (two gone, one new: not certain).
                rivals = [o for o in older_records() if o.id != p.id
                          and _could_be_same(reg, o, target, together, seen_on) and said(o, target) != aq.DIFFERENT
                          and _certain(reg, o, target, seen_on, dates) and o.id not in together.get(p.id, ())]
                if rivals:
                    continue
            else:
                continue
            _merge_into(reg, p, target)
            changed = True
            break
    together, seen_on = views()
    questions: list[IdentityQuestion] = []
    for p in older_records():
        fits = [q for q in reg.people.values() if _could_be_same(reg, p, q, together, seen_on)
                and said(p, q) is None]
        if len(fits) > 3:
            continue                                # a name many villagers had: nothing to go on
        for q in fits:
            what = []
            if p.head != q.head:
                what.append(f"head {p.head} -> {q.head}")
            if p.body != q.body:
                what.append(f"body {p.body} -> {q.body}")
            why = (f"The looks changed ({', '.join(what)}) and no record says so" if what else "")
            unsure = []
            if len(fits) > 1:
                unsure.append(f"{len(fits)} villagers called {q.name} could be them")
            elif _likes_fit(p, q) is False:
                unsure.append("their likes differ")
            else:
                unsure.append("nothing in the records ties them for certain (no unbroken Village History, no "
                              "parent named on both)")
            questions.append(IdentityQuestion(
                p.key, q.key, _person_text(reg, p, seen_on), _person_text(reg, q, seen_on),
                (why + "; " if why else "") + "; ".join(unsure) + ". A change of looks or title never means a "
                "villager left: Same joins them; Different keeps them apart.", q.age))
    questions.sort(key=lambda q: (q.age is None, -(q.age or 0), q.newer))
    return questions


def _logged_renames(reg: _Registry, folder: Path, game: int, slot: int) -> None:
    """The "Name changed" records (the Births and Conceptions log): the record under the old name and
    the one under the new name, with the same looks, are ONE villager under the new name (the owner,
    2026-10-18: Mahalo Makawee was the founder Tamil Makawee, renamed; the arrival backfill had written
    a second "How: unknown" Arrived record under the new name, so the founder showed as an arrival).
    In log order, so a chain of renames ends on the last name.  Never when the old name and looks are a
    living villager's (a child given the old name), when the old name's record is dead or gone, or when
    both have a Birth record of their own: those stay apart, and the reconciliation asks the player."""
    import vv_log_additions as additions
    checker = tools.load_checker()
    villages = additions.current_villages(folder, game, slot)
    births = [path for path in checker.log_files(folder) if "Births and Conceptions" in path.name]
    for path in sorted(births, key=lambda q: [int(s) if s.isdigit() else s for s in re.split(r"(\d+)", q.name)]):
        for b in additions.blocks(path):
            if b.heading != "Name changed" or not b.of(slot, game, villages):
                continue
            new, head, body = b.identity
            old = b.value("Old name")
            if not new or not old or old == new or head is None or body is None:
                continue
            old_key, new_key = reg.current((old, head, body)), reg.current((new, head, body))
            if old_key not in reg.by_key or new_key not in reg.by_key:
                continue
            p, q = reg.people[reg.by_key[old_key]], reg.people[reg.by_key[new_key]]
            if p.id == q.id or p.alive or p.gone or (p.birth_record is not None and q.birth_record is not None):
                continue
            _merge_renamed(reg, p, q)


def _answered_renames(reg: _Registry, folder: Path, game: int, slot: int, tree_answers: dict,
                      notes: list[str]) -> None:
    """The renames the player answered in Check / Repair Saves & Logs (the Log Decisions file, kind
    "reconcile"): a "rename|OLD|head|body|NEW" question answered "Keep as is: NEW is right (I renamed
    them)" joins the record under the old name to the one under the new name as ONE villager, as a "Name
    changed" record does (_logged_renames).  The owner, 2026-10-18: Waiata Wambui was renamed City Wambui
    with no "Name changed" record, and the tree showed Waiata Wambui as "(left the village)".  The same in
    all five games: the question, its key and its answer are the reconciliation's, which reads every game
    alike.  Read only.  The same limits: never when the old name and looks are a living villager's, when
    the old name's record is dead or gone, or when both have a Birth record of their own.  A Family Tree
    answer that keeps the two apart ("old") contradicts it: they stay apart and the notes say so."""
    import vv_log_additions as additions
    import vv_reconcile as reconcile
    try:
        answers = reconcile.answered(folder, game, slot, additions.current_villages(folder, game, slot))
    except (OSError, ValueError):
        return
    for field in sorted(answers):
        parts = field.split("|")
        if len(parts) != 5 or parts[0] != "rename":
            continue
        _topic, old, head_text, body_text, new = parts
        if answers[field] != f"{reconcile.KEEP}: {new} is right (I renamed them)":
            continue
        try:
            head, body = int(head_text), int(body_text)
        except ValueError:
            continue
        if not old or not new or old == new:
            continue
        old_key, new_key = reg.current((old, head, body)), reg.current((new, head, body))
        if old_key not in reg.by_key or new_key not in reg.by_key:
            continue
        p, q = reg.people[reg.by_key[old_key]], reg.people[reg.by_key[new_key]]
        if p.id == q.id or p.alive or p.gone or (p.birth_record is not None and q.birth_record is not None):
            continue
        if tree_answers.get(rename_key(old, head, body)) == "old":
            notes.append(f"{old} and {new} (head {head}, body {body}): Check Saves & Logs was answered \"{new} "
                         f"is right (I renamed them)\", but the Family Tree Maker was answered \"keep {old} as a "
                         "separate villager\", so they were not joined. Change one answer to settle it.")
            continue
        _merge_renamed(reg, p, q)


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
            if (old_head, old_body) == (new_head, new_body):
                continue        # the mask alone changed ("Old mask" / "New mask"): the same look on the tree
            old, new = (name, old_head, old_body), (name, new_head, new_body)
            reg.relooked.pop(new, None)
            reg.relooked[old] = new


@dataclass
class _Vv1Entry:
    """One record of A New Home's Parents (A New Home) sidecar: who held it (head and body None where
    an older build's roster did not keep them), and the parents and the pregnancy's father it
    names -- each (name, head, body), or None when not recorded."""
    who: tuple                      # (name, gender 1/2, family scalar, head, body)
    departed: bool                  # the record was empty: this is the villager who had held it
    father: Key | None
    mother: Key | None
    stash: Key | None


def _vv1_sidecar(folder: Path, slot: int) -> list[_Vv1Entry]:
    """A New Home's Parents (A New Home) sidecar, the companion's record of every villager's parents
    (native/vv1_parentage), under the new folder name or the old one (vv_save_layout); nothing when
    the file is missing, unreadable or not a VP02 file of this length written for this slot."""
    import vv_save_layout as layout
    name = f"Virtual Villagers 1 Parentage Records - Save {slot}.dat"
    path = layout.route(Path(folder), f"{layout.DATA}\\{layout.PARENTS_VV1}\\{name}")
    try:
        data = path.read_bytes()
    except OSError:
        return []
    if len(data) < VV1_SIDECAR_SIZE or data[:4] != VV1_SIDECAR_MAGIC or _i32(data, 8) != slot:
        return []
    import vv1_parents_restore as parents_file
    # The departed list after the 256 entries: room for every villager who ever lived, a village at the
    # 256 cap included (native/vv1_parentage g_departed).  A file whose list is not the companion's is
    # one the companion itself sets aside: nothing is read from it.
    departed_list = parents_file.departed_list(data)
    if departed_list is None:
        return []
    cut = VV1_SIDECAR_NAME - 1

    def person(buf: bytes, e: int, looks: int, at: int) -> Key | None:
        # Every value is stored +1: 0 is "not recorded", and head 0 / body 0 are real looks.
        name, head, body = _cstr(buf, e + at, VV1_SIDECAR_NAME)[:cut], buf[e + looks], buf[e + looks + 1]
        return (name, head - 1, body - 1) if name and head and body else None

    places = [(data, 12 + i * VV1_SIDECAR_OCCUPANT, 12 + 256 * VV1_SIDECAR_OCCUPANT + i * VV1_SIDECAR_ENTRY)
              for i in range(256)]
    places += [(item, 0, VV1_SIDECAR_OCCUPANT) for item in departed_list]
    out = []
    for buf, occ, e in places:
        gender, departed, head, body = buf[occ], buf[occ + 1], buf[occ + 2], buf[occ + 3]
        if gender not in (1, 2):
            continue
        who = (_cstr(buf, occ + 8, VV1_SIDECAR_NAME)[:cut], gender, _i32(buf, occ + 4),
               head - 1 if head and body else None, body - 1 if head and body else None)
        entry = _Vv1Entry(who, bool(departed) or buf is not data, person(buf, e, 0, 8), person(buf, e, 2, 36),
                          person(buf, e, 4, 64))
        if entry not in out:                # the same villager with the same entry: one entry
            out.append(entry)
    return out


def _vv1_fits(who: tuple, living: tuple) -> bool:
    name, gender, family, head, body = who
    _pid, l_name, l_gender, l_family, l_head, l_body = living
    return (name, gender, family) == (l_name, l_gender, l_family) \
        and (head is None or (head, body) == (l_head, l_body))


def _vv1_from_sidecar(reg: _Registry, folder: Path, slot: int) -> None:
    """What A New Home keeps nowhere and the later games keep on the villager's own record
    (`_save_people`), from the VV1 Parentage companion's sidecar: each villager's parents, and the
    expected father of each pregnancy.

    After the Births and Conceptions log, which wins where it speaks: it is written with the save,
    and it is what the companion itself trusts over its own table (the first-load check,
    native/vv1_parentage/vv1_crosscheck.inc).  So the expected father is her last Conception
    record's, else the father the sidecar stashed against her at that conception
    (vv1_expected_father); a parent is the Birth record's, else the sidecar's.

    An entry is a living villager's only when its roster names exactly one living villager -- name,
    sex, family number and, where it kept them, head and body -- and no other entry of the file fits
    her; anything else is left unknown rather than guessed (patcher data follows the villager, never
    a record number).  A record whose villager has died keeps her entry, flagged `departed`: it is
    hers when her name and looks are a villager the logs know and the file holds no other such
    entry."""
    expecting = {pid for pid, *_ in reg.vv1_living if reg.people[pid].expecting}
    for pid in expecting:
        father = reg.conceptions.get(reg.people[pid].key, (None, 1))[0]
        if father and father[0]:
            reg.expected[pid] = father
    entries = _vv1_sidecar(folder, slot)
    present = [e for e in entries if not e.departed]
    for e in entries:
        if e.departed:
            name, _g, _f, head, body = e.who
            if head is None or sum(1 for o in entries if o.who == e.who) != 1:
                continue
            pid = reg.by_key.get(reg.current((name, head, body)))
            if pid is None or reg.people[pid].alive:
                continue
            target = reg.people[pid]
        else:
            holders = [v for v in reg.vv1_living if _vv1_fits(e.who, v)]
            if len(holders) != 1 or sum(1 for o in present if _vv1_fits(o.who, holders[0])) != 1:
                continue
            target = reg.people[holders[0][0]]
            if e.stash is not None and target.id in expecting and target.id not in reg.expected:
                reg.expected[target.id] = e.stash
        for key, attr, sex in ((e.father, "father", "Male"), (e.mother, "mother", "Female")):
            if key is not None and getattr(target, attr) is None:
                parent = reg.get(*key)
                parent.sex = parent.sex or sex
                setattr(target, attr, parent.id)

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
    # A default father ("?", "Joey", "Unknown") is a name only: never numbered (the owner, v1.35.85).
    for p in village.known():
        if getattr(p, "placeholder", False):
            p.number = None
    counted = village.villagers()
    for g in sorted({p.generation for p in counted}):
        row = [p for p in counted if p.generation == g]
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

def is_placeholder_father(game: int, p: Person) -> bool:
    """A default father (GAME_DEFAULT_FATHERS, FALLBACK_FATHER) rather than a villager: one of those
    names and looks, and nothing that only a real villager has -- alive in the save, parents of his
    own, an Arrived, Death or Disappeared record."""
    if p.key not in GAME_DEFAULT_FATHERS.get(game, frozenset()) and p.key != FALLBACK_FATHER:
        return False
    return not (p.alive or p.gone or p.arrived or p.father is not None or p.mother is not None)


def real_parents(people: dict[int, Person], p: Person) -> list[int]:
    """The parents a villager shares blood with: a default father stands for "no man named", so two
    children of the Gong's "?" or of "Unknown" are not brothers through him."""
    return [q for q in (p.father, p.mother) if q is not None and not people[q].placeholder]


class Kinship:
    """Coefficients of kinship over the recorded family (Wright): two villagers' chance of
    sharing a gene by descent.  Twice it is how related they are: 1/2 a parent, child or full
    sibling, 1/4 a half sibling, grandparent, aunt or uncle, 1/8 a first cousin.  A default father
    (is_placeholder_father) is nobody's kin."""

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
            parents = real_parents(self.people, p)
            inbred = self.phi(*parents) if len(parents) == 2 else Fraction(0)
            return (1 + inbred) / 2
        if self._order(a) < self._order(b):
            a, b = b, a
        key = (a, b)
        if key not in self.memo:
            p = self.people[a]
            total = Fraction(0)
            for parent in real_parents(self.people, p):
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
            for parent in real_parents(village.people, p):
                if parent not in out or out[parent] > depth + 1:
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
    real_a, real_b = set(real_parents(village.people, pa)), set(real_parents(village.people, pb))
    shared_parents = real_a & real_b
    if shared_parents:
        both = len(real_a) == 2 and real_a == real_b
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

# How the pairings can be listed: (words in the report, ascending, descending).
LIST_BY = {
    "default": ("Listed in the default order (least related first)", "", ""),
    "generation": ("Listed by generation (the later generation of the pair, then the other)",
                    "oldest generation at the top", "latest generation at the top"),
    "age": ("Listed by age (the woman's, then the man's)", "youngest at the top", "oldest at the top"),
    "number": ("Listed by family tree number (the woman's, then the man's)",
               "lowest number at the top", "highest number at the top"),
}


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
    one_family_per_partner: bool = False  # no partner from a family they already have a child with
    prefer_previous_partners: bool = True   # established couples first (the owner, 2026-10-08)
    prefer_fresh_blood: bool = True
    # How the pairings are LISTED (the owner, 2026-10-10: "prioritize latest generation", then "List pairings by"):
    # only the order changes, never who may pair with whom.  The default is the newest generation first.
    list_by: str = "generation"            # one of LIST_BY
    list_direction: str = "descending"    # "ascending" or "descending"

    @property
    def prefer_latest_generation(self) -> bool:
        return self.list_by == "generation" and self.list_direction == "descending"

    # How the report shows ages, not a pairing rule (the owner, 2026-10-08: "a toggle to turn Age
    # Units on and off"): "1379 game units (68 years old)", or "68 years old" alone.
    show_age_units: bool = False

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
                            (self.prefer_previous_partners, "Previous partners first"),
                            (self.prefer_fresh_blood, "Fresh blood first")):
            if flag:
                out.append(words)
        out.append(self.listing())
        return out

    def listing(self) -> str:
        by = LIST_BY.get(self.list_by, LIST_BY["default"])
        if self.list_by not in LIST_BY or self.list_by == "default":
            return by[0]
        down = self.list_direction != "ascending"
        return f"{by[0]}, {by[2] if down else by[1]}"


@dataclass
class Pair:
    man: Person
    woman: Person
    related: Fraction
    relation: str
    shared: int                          # recorded ancestors they share
    born: int = 0                        # children they have had together (the dead too)
    expected: int = 0                    # babies on the way between them

    @property
    def together(self) -> str:
        """Whether the two have had a child together before (the owner, 2026-10-09: "for the Matchmaker,
        can you mention if the two villagers have previously had a child?"), as the report says it."""
        parts = []
        if self.born:
            parts.append("have had a child together before" if self.born == 1
                         else f"have had {self.born} children together before")
        if self.expected:
            parts.append("a baby on the way together" if self.expected == 1
                         else f"{self.expected} babies on the way together")
        return ", and ".join(parts)

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
             shared: dict, partners: dict[int, set[tuple[str, int]]] | None = None) -> str | None:
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
    # Wanjiko is not offered a Wanjiko II -- but the same partner again always is (the owner, 2026-10-08:
    # "stop him only from moving on to a second person from the same family").
    if rules.one_family_per_partner and partners is not None and (
            any(family == _last_name(woman.name).casefold() and other != woman.id
                for family, other in partners.get(man.id, ()))
            or any(family == _last_name(man.name).casefold() and other != man.id
                   for family, other in partners.get(woman.id, ()))):
        return "already has a child with another of that family"
    return None


def _partner_families(village: Village) -> dict[int, set[tuple[str, int]]]:
    """Each parent -> (last name, numbers dropped; who) of everyone they have a child, born or on the
    way, with."""
    out: dict[int, set[tuple[str, int]]] = {}
    for child in village.people.values():
        if child.father is None or child.mother is None or village.people[child.father].placeholder:
            continue            # a default father ("?", "Joey", "Unknown") is no family
        for one, other in ((child.father, child.mother), (child.mother, child.father)):
            name = _last_name(village.people[other].name).casefold()
            if name:
                out.setdefault(one, set()).add((name, other))
    return out


def suggest(village: Village, rules: Rules) -> tuple[list[Pair], dict[int, list[Pair]], list[Pair]]:
    """(one-to-one suggested pairs, every allowed partner per woman, the least related pairs when
    the rules allow none).  Pairs are ranked couples who already have a child together first (with
    that rule), then least related, then fresh blood (with that rule), then closest in age."""
    kin = Kinship(village)
    men, women = candidates(village, rules)
    allowed: list[Pair] = []
    every: list[Pair] = []
    up = {p.id: ancestors(village, p.id) for p in men + women}
    partners = _partner_families(village)
    born: dict[tuple, int] = {}
    expected: dict[tuple, int] = {}
    for c in village.people.values():
        if c.father is not None and c.mother is not None:
            tally = expected if c.upcoming else born
            tally[(c.father, c.mother)] = tally.get((c.father, c.mother), 0) + 1
    for w in women:
        for m in men:
            related = kin.relatedness(m.id, w.id)
            relation = relationship(village, m.id, w.id)
            common = {c: (up[m.id][c], up[w.id][c]) for c in set(up[m.id]) & set(up[w.id])}
            pair = Pair(m, w, related, relation, len(common), born.get((m.id, w.id), 0), expected.get((m.id, w.id), 0))
            every.append(pair)
            if _blocked(rules, m, w, relation, related, common, partners) is None:
                allowed.append(pair)

    def fresh(p: Person) -> int:
        return 0 if p.father is None and p.mother is None else 1

    # Couples who already have a child together, born or on the way (the owner, 2026-10-08:
    # "Prioritize previous partners (so that established couples can make more children together)").
    couples = {(c.father, c.mother) for c in village.people.values()
               if c.father is not None and c.mother is not None}

    sign = -1 if rules.list_direction != "ascending" else 1

    def listkey(pair: Pair) -> tuple:
        """The listing order the player chose, a key (all zero for the default order); ties keep the ranking."""
        m, w = pair.man, pair.woman
        if rules.list_by == "generation":
            return (sign * max(m.generation, w.generation), sign * min(m.generation, w.generation))
        if rules.list_by == "age":
            # An age of 0 is a real age; an unknown one goes last either way.
            return (w.age is None, sign * (w.age or 0), m.age is None, sign * (m.age or 0))
        if rules.list_by == "number":
            return (w.number is None, sign * (w.number or 0), m.number is None, sign * (m.number or 0))
        return (0, 0)

    def rank(pair: Pair) -> tuple:
        gap = abs((pair.man.age or 0) - (pair.woman.age or 0))
        established = rules.prefer_previous_partners and (pair.man.id, pair.woman.id) in couples
        newest = (listkey(pair) if rules.list_by == "generation" else (0, 0))
        return (newest, not established, pair.related,
                (fresh(pair.man) + fresh(pair.woman)) if rules.prefer_fresh_blood else 0,
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
        options = per_woman.get(woman, [])
        if rules.list_by == "generation":
            # A free man in her own best order before moving another woman off hers, so the newest
            # generation's couples are not split to pair them with an older generation (stable: the
            # order among the free and among the taken is unchanged).
            options = ([p for p in options if p.man.id not in partner]
                       + [p for p in options if p.man.id in partner])
        for pair in options:
            if pair.man.id in seen:
                continue
            seen.add(pair.man.id)
            if pair.man.id not in partner or place(partner[pair.man.id].woman.id, seen):
                partner[pair.man.id] = pair
                return True
        return False

    for woman in sorted(per_woman, key=lambda w: rank(per_woman[w][0])):
        place(woman, set())
    one_to_one = sorted(sorted(partner.values(), key=rank), key=listkey)
    fallback = [] if allowed else sorted(sorted(every, key=rank)[:10], key=listkey)
    # The chosen listing order, a stable sort: the women, and each woman's partners, keep the ranking in ties.
    for wid in per_woman:
        per_woman[wid] = sorted(per_woman[wid], key=listkey)
    per_woman = dict(sorted(per_woman.items(), key=lambda item: listkey(item[1][0])))
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
    "oldest": "By age now, oldest first",
    "youngest": "By age now, youngest first",
    # The owner (2026-10-20): "oldest first" and "in order of appearance" are the same thing -- the older
    # villagers appear first -- so the default says both.
    "appearance": "Oldest first (order of appearance)",
}


def duplicate_names(village: Village, order: str = "appearance", reserved: set[str] = frozenset(),
                    leave: set[int] = frozenset(), weight: dict[int, int] | None = None,
                    blocks: dict[int, list[str]] | None = None) -> dict[int, str]:
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
    # Namesakes are told by the WHOLE name, first and last, a number they already carry set aside (the
    # owner, 2026-10-08: "roman numerals should be given for people who have both the same first and
    # last name (Suki Wikimak I, Suki Wikimak II)"): two Sukis numbered before they had last names,
    # "Suki Alosaka I" and "Suki Wanjiko II", are no namesakes now -- and keep their numbers (below).
    # An older record the Family Tree Maker still asks about ("the same villager?", IdentityQuestion) is
    # never a namesake until the player says Different: a change of looks or title gives no number.
    asked = {q.older for q in getattr(village, "identity_questions", [])}
    leave = set(leave) | {p.id for p in village.known() if p.key in asked and not p.alive}
    holders: dict[str, list[Person]] = {}
    for p in sorted(village.known(), key=keys[order]):
        if p.id not in leave:
            holders.setdefault(unnumbered(p.name), []).append(p)
    # A NUMBER IS KEPT FOR LIFE (the owner, 2026-10-20): "a villager who has a number KEEPS it, even after
    # their namesake dies or leaves"; numbering only ever ADDS numbers -- it never removes or lowers one
    # -- and a new namesake gets the next free number after the highest used before them, the dead and
    # gone included, so no number is ever given twice.  Every number any record of the name carries
    # (`reserved` and the villagers left out too) counts as used.
    used: dict[str, set[int]] = {}
    for p in village.known():
        base, value = unnumbered(p.name), roman_value(p.name.rsplit(" ", 1)[-1])
        if base != p.name and value:
            used.setdefault(base, set()).add(value)
    for taken_name in reserved:
        base, value = unnumbered(taken_name), roman_value(taken_name.rsplit(" ", 1)[-1])
        if base != taken_name and value:
            used.setdefault(base, set()).add(value)
    out = {}
    for name, ps in holders.items():
        if sum((weight or {}).get(p.id, 1) for p in ps) < 2:
            continue                            # no namesake: the name stays as it is, number and all
        numbers = used.setdefault(name, set())
        seen: set[str] = set()
        before = 0                              # the highest number of the namesakes before this one
        for p in ps:
            value = roman_value(p.name.rsplit(" ", 1)[-1]) if p.name != name else 0
            given = []
            if value and p.name not in seen:
                seen.add(p.name)                # a number of their own: kept (never lowered or removed)
                before = max(before, value)
                given.append(p.name)
            # Not numbered yet (or a number another namesake before them has): the lowest number never
            # used that comes after every namesake before them.  One Person standing for several
            # villagers (namesakes with the same looks) gets one for each (`blocks`, first to last).
            for _ in range((weight or {}).get(p.id, 1) - len(given)):
                n = before + 1
                while n in numbers:
                    n += 1
                numbers.add(n)
                before = n
                given.append(f"{name} {roman(n)}")
            if given[0] != p.name:
                out[p.id] = given[0]
            if blocks is not None and len(given) > 1:
                blocks[p.id] = given
    return out


_ROMAN_VALUES: dict[str, int] = {}


def roman_value(word: str) -> int:
    """The number a Roman numeral as roman() writes it stands for; 0 for any other word."""
    if not _ROMAN_VALUES:
        _ROMAN_VALUES.update({roman(n): n for n in range(1, 4000)})
    return _ROMAN_VALUES.get(word, 0)


def unnumbered(name: str) -> str:
    """A name without the Roman number Number Duplicate Names gave it ("Suki Wanjiko II" -> "Suki
    Wanjiko"); a one-word name is never cut to nothing."""
    words = name.split(" ")
    if len(words) > 1 and re.fullmatch(r"[IVXLCDM]+", words[-1]):
        return " ".join(words[:-1])
    return name


def numbered(p: Person) -> str:
    """"#12 Name", or the name alone for one with no number on the tree (taken off it)."""
    return f"#{p.number} {p.name}" if p.number is not None else p.name


def describe_person(village: Village, p: Person) -> str:
    if p.upcoming:
        return f"{p.name} (on the way)"
    if p.placeholder:
        return f"{p.name} (a default father: a name only, not a villager)"
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
        born = [p for p in group if not p.upcoming and not p.placeholder]     # a default father: a name only
        coming = sum(1 for p in group if p.upcoming)
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
        elif p.placeholder:
            how = "named as a father only"
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


def _nobody_to_pair(village: Village, rules: Rules) -> str:
    """Why the rules leave no man and woman to pair at all (candidates() gives no man or no woman), in
    words: how many living villagers of that sex there are, and which rule leaves each one out."""
    men, women = candidates(village, rules)
    ages = rules.describe()[0].lower()
    parts = []
    for sex, chosen, word in (("Female", women, "woman"), ("Male", men, "man")):
        if chosen:
            continue
        living = [p for p in village.living() if p.sex == sex and not p.heathen]
        if not living:
            parts.append(f"there is no living {word}")
            continue
        aged = [p for p in living if _age_ok(p, rules) and not (village.game == 1 and p.family == 199)]
        expecting = [p for p in aged if rules.not_expecting and p.expecting]
        noun = "woman" if sex == "Female" else "man"
        nouns = "women" if sex == "Female" else "men"
        why = [f"{len(living) - len(aged)} not {ages}"] if len(aged) < len(living) else []
        if expecting:
            why.append(f"{len(expecting)} already expecting")
        parts.append(f"no {noun} can be paired (of the {len(living)} living {nouns if len(living) != 1 else noun}, "
                     f"{' and '.join(why)})")
    return ("; ".join(parts) or "no man and woman can be paired") + "."


def pair_report(village: Village, rules: Rules, game_title: str) -> str:
    """The pairing suggestions (their own button: the owner, "get rid of the pairings on the family
    tree.  there should be a separate button for pairing suggestions")."""
    people = village.people
    one_to_one, per_woman, fallback = suggest(village, rules)

    def age(p: Person) -> str:
        if rules.show_age_units or p.age is None:
            text = p.age_text()
        else:
            text = f"died at {p.years} years old" if p.gone == "died" else f"{p.years} years old"
        return f"{text}, Generation {roman(p.generation)}"
    lines = [f"{game_title} -- Village Matchmaker",
             f"Village: {village.tribe} (Save {village.slot})" if village.tribe else f"Save {village.slot}",
             "",
             "Relatedness counts only the family the save and the patcher's logs record; ancestry from "
             "before the logs began is unknown.  The number before a name is its number on the family tree.",
             ""]
    lines.append("== Pairing rules ==")
    lines += [f"  {r}" for r in rules.describe()] or ["  (none)"]
    lines.append("")
    # In the order "List pairings by" chose (the rules above say which); least related first within it.
    lines.append("== Suggested pairs (each villager once) ==")
    if one_to_one:
        for n, pair in enumerate(one_to_one, 1):
            lines.append(f"  {n}. {numbered(pair.man)}, {age(pair.man)}, and "
                         f"{numbered(pair.woman)}, {age(pair.woman)}: {pair.relation}, "
                         f"related {pair.percent:g}%" + (f"; {pair.together}" if pair.together else ""))
    elif not fallback:
        # Nobody to pair at all: never "the least related pairs available" over an empty list.
        lines.append("  No pair meets every rule: " + _nobody_to_pair(village, rules))
    else:
        lines.append("  No pair meets every rule.  The least related pairs available:")
        for pair in fallback:
            lines.append(f"    {pair.man.name} (Generation {roman(pair.man.generation)}) and "
                         f"{pair.woman.name} (Generation {roman(pair.woman.generation)}): {pair.relation}, related {pair.percent:g}%"
                         + (f"; {pair.together}" if pair.together else ""))
    lines.append("")
    lines.append("== Every allowed partner, per woman ==")
    if not per_woman:
        lines.append("  (none)")
    for wid, pairs in per_woman.items():
        lines.append(f"  {people[wid].name}, {age(people[wid])}:")
        for pair in pairs:
            lines.append(f"    {pair.man.name}, {age(pair.man)}: {pair.relation}, related {pair.percent:g}%"
                         + (f"; {pair.together}" if pair.together else ""))
    lines.append("")
    return "\n".join(lines)
