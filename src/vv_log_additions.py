"""Repair Saves & Logs: what older log records lack, and adding it (all five games).

The owner (2026-10-06): Check Saves & Logs and Repair Saves & Logs ask the player whether to
add, retroactively, what records written by an older patcher lack -- the Sex
line, the Special villager title, the Custom title, the Mask, Twin / Triplet
(and, since, New Believers' Faction line) -- and "CHECK ALL SAVES, DAT FILES AND EXES. IF EVER UNSURE, ASK THE PLAYER".

So every kind is planned from what the save, the patcher's own files and the
logs themselves settle, and whatever they cannot settle becomes a Question the
player answers in the Repair Saves & Logs window; an unanswered question ("Don't
know") adds nothing.  Planning only reads.  Applying backs every log up
beside itself first (never replacing a backup), rewrites it through a
temporary file and lists what it added in the Repairs log.

Where the current truth comes from: the slot's Village Population page, which
the game rewrites at every save with each living villager's Custom title,
Special villager title and Mask (a page an older patcher wrote has no Mask
lines: then no mask is known until the village has been saved once with this
build), the save, and each record's own lines (its skills, its grave).  Older
History snapshots are dated, so a title or mask a villager has now is asked
about from a date: the player picks the first snapshot it belongs in.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import vv_log_tools as tools

DONT_KNOW = "Don't know (add nothing)"

# What each kind checked, for its Repairs log record (src/vv_log_tools.py note_word_repair).
CHECKED = {
    "sex": "the villagers in older records with no Sex line, against the save, the logs, the game's own "
           "name lists and the player's answers",
    "special": "the older records with no Special villager line, against each record's skills and grave, "
               "the Village Population page and the player's answers",
    "custom": "the older Village History snapshots of villagers with a Custom title, from the date the "
              "player chose",
    "mask": "the older Village History snapshots of villagers who wear a mask, from the date the player chose",
    "born_as": "the older Birth records, against the mother's Conception record and the player's answers",
    "golden": "the Golden Child's Arrived records, against the pregnancies with no Birth and the player's answers",
    "appearance": "the villagers whose look changed with no Appearance changed record, against the save, the "
                  "logs and the player's answers",
    "faction": "New Believers' older Village History and Village Population records with no Faction line, "
               "against each record's own title, the latest Village Population page, the conversions and "
               "departures to the Heathens the logs record, and the player's answers",
}
ADDED = {"sex": "Sex added", "special": "Special villager added", "custom": "Custom title added",
         "mask": "Mask added", "born_as": "Born as added", "golden": "Golden Child's Birth added",
         "appearance": "Appearance changed record added",
         "faction": "Faction added"}
FROM_NOW = "Only from now on (add nothing)"

# The order the lines take under a villager's name (as the exporters print them).
RANK = {"custom": 1, "special": 2, "mask": 3}


@dataclass
class Question:
    key: str
    text: str
    options: list[str]
    default: str


@dataclass
class Insert:
    path: Path
    after: int                              # the line index the new line follows
    rank: int                               # several lines after one line: their order
    line: str | None = None                 # decided
    question: str | None = None             # ...or the answer decides
    by_answer: dict[str, str] = field(default_factory=dict)


@dataclass
class Kind:
    id: str
    label: str                              # the checklist's words
    inserts: list[Insert] = field(default_factory=list)
    questions: dict[str, Question] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def decided(self) -> int:
        return sum(1 for i in self.inserts if i.line)

    @property
    def asked(self) -> int:
        return len(self.questions)


# ---------------------------------------------------------------------------
# Reading the logs
# ---------------------------------------------------------------------------

PERSON_HEAD = re.compile(r"^(Villager \d+|Death \d+|Disappeared|Arrived \d+|Unaccounted \d+)\s*$")
SNAPSHOT = re.compile(r"^=== .* -- (.*) ===\s*$")
VILLAGE = re.compile(r"^Village: .*\(Save (\d)\)\s*$")
# The game a file's name ("Virtual Villagers 3 Deaths Log 1.txt"), a History snapshot
# ("=== Virtual Villagers 3 -- ...") or a Population page's title names.
GAME_IN_NAME = re.compile(r"^Virtual Villagers (\d) ")
GAME_IN_HEADING = re.compile(r"^(?:=== )?Virtual Villagers (\d)\b")
SPECIAL_TITLES = ("Tribal Chief", "Retired Heathen Chief", "Golden Child", "Esteemed Elder", "Scholar")


@dataclass
class Block:
    path: Path
    start: int                              # line index of the heading
    lines: list[str]
    slot: int | None                        # the "Village: ... (Save n)" it is under
    date: str | None                        # a History snapshot's date
    game: int | None = None                 # the game the file or its snapshot names
    village: str | None = None              # the whole "Village: <name> (Save n)" it is under

    def of(self, slot: int, game: int, villages: set[str] | None = None) -> bool:
        """Under this slot's village of this game (Codex, #553: two games may share a folder, and
        a slot reused after Start Over keeps the erased village's History snapshots): `villages`
        are the headers the slot's current village has had (current_villages)."""
        return (self.slot == slot and (self.game is None or self.game == game)
                and (villages is None or self.village in villages))

    @property
    def heading(self) -> str:
        return self.lines[0].strip()

    def value(self, label: str, indent: str = "  ") -> str | None:
        for line in self.lines:
            if line.startswith(f"{indent}{label}:"):
                return line.split(":", 1)[1].strip()
        return None

    def index_of(self, label: str, indent: str = "  ") -> int | None:
        for k, line in enumerate(self.lines):
            if line.startswith(f"{indent}{label}:"):
                return self.start + k
        return None

    def int_value(self, label: str) -> int | None:
        v = self.value(label)
        try:
            return int(v) if v is not None else None
        except ValueError:
            return None

    @property
    def identity(self) -> tuple:
        return (self.value("Name"), self.int_value("Head"), self.int_value("Body"))

    @property
    def person(self) -> tuple | None:
        """Name, Likes and Dislikes: what a Change Appearance leaves alone, so a snapshot written
        before the villager's head or body changed still finds them (Codex, #553)."""
        key = (self.value("Name"), self.value("Likes"), self.value("Dislikes"))
        return key if None not in key else None

    @property
    def skills(self) -> list[int]:
        out = []
        inside = False
        for line in self.lines:
            if line.startswith("  Skills:"):
                inside = True
                continue
            if inside:
                m = re.match(r"^    \S+\s+(-?\d+)\s*$", line)
                if not m:
                    break
                out.append(int(m.group(1)))
        return out


def read_lines(path: Path) -> list[str]:
    return path.read_bytes().decode("latin-1").replace("\r\n", "\n").split("\n")


def blocks(path: Path, lines: list[str] | None = None) -> list[Block]:
    """Every blank-line separated block, with the village slot and snapshot date above it."""
    lines = read_lines(path) if lines is None else lines
    out: list[Block] = []
    slot = date = village = None
    named = GAME_IN_NAME.search(path.name)
    game = int(named.group(1)) if named else None
    start = None
    for i, line in enumerate(lines + [""]):
        if line.strip() and start is None:
            start = i
        if not line.strip() and start is not None:
            chunk = lines[start:i]
            offset = 0
            # Headings: a History snapshot's "=== ... ===", a "Village: ... (Save n)", and a
            # file's own title line (the Village Population page's "Virtual Villagers N ...").
            while offset < len(chunk) and (SNAPSHOT.match(chunk[offset]) or VILLAGE.match(chunk[offset])
                                           or chunk[offset].startswith("Virtual Villagers ")):
                m = SNAPSHOT.match(chunk[offset])
                if m:
                    date = m.group(1).strip()
                m = GAME_IN_HEADING.match(chunk[offset])
                if m:
                    game = int(m.group(1))
                m = VILLAGE.match(chunk[offset])
                if m:
                    slot = int(m.group(1))
                    village = chunk[offset].rstrip()
                offset += 1
            if offset < len(chunk):
                out.append(Block(path, start + offset, chunk[offset:], slot, date, game, village))
            start = None
    return out


RENAMED = re.compile(r"^Tribe renamed from (.+) to (.+) on \d{4}-\d{2}-\d{2}")


def current_villages(folder: Path, game: int, slot: int) -> set[str] | None:
    """Every "Village: <name> (Save n)" header the slot's current village has had: its name in
    the save, and each name a "Tribe renamed from <old> to <new>" note says it had before (Rename
    Tribe, docs/rename-tribe.md).  A note counts only under this game's and slot's village, under a
    header of a name the chain already has (Codex, #553: another village's rename is not this
    one's).  None when the save cannot be read (then every header of the slot is taken)."""
    import vv_tribe_rename
    checker = tools.load_checker()
    games = {g.number: g for g in vv_tribe_rename.GAMES}
    try:
        data = (Path(folder) / f"{checker.SAVE_STEMS[game]}{slot}.ldw").read_bytes()
        name = vv_tribe_rename.save_name(games[game], data)
    except (OSError, KeyError, ValueError):
        return None
    if not name:
        return None
    names = {name}
    notes = []
    for path in checker.log_files(Path(folder)):
        try:
            found = blocks(path)
        except OSError:
            continue
        for b in found:
            if b.slot != slot or (b.game is not None and b.game != game):
                continue
            notes += [(*m.groups(), b.village) for m in map(RENAMED.match, b.lines) if m]
    grew = True
    while grew:
        grew = False
        for old, new, under in notes:
            known = {vv_tribe_rename.village_header(n, slot) for n in names | {old}}
            if new in names and old not in names and under in known:
                names.add(old)
                grew = True
    return {vv_tribe_rename.village_header(n, slot) for n in names}


def person_blocks(folder: Path, slot: int, game: int) -> list[Block]:
    """Every one-villager record (History / Population snapshot entries, Deaths, Disappeared,
    Arrived, Unaccounted) under this slot's village, in every log."""
    checker = tools.load_checker()
    out = []
    villages = current_villages(folder, game, slot)
    for path in checker.log_files(folder):
        for b in blocks(path):
            if b.of(slot, game, villages) and PERSON_HEAD.match(b.heading):
                out.append(b)
    return out


def population_page(folder: Path, slot: int, game: int) -> tuple[Path | None, dict[tuple, Block]]:
    """The slot's latest Village Population page: each living villager by (name, head, body)."""
    checker = tools.load_checker()
    for path in checker.numbered(folder / checker.LOGS / "Tribe Population", "Village Population"):
        villages = current_villages(folder, game, slot)
        found = [b for b in blocks(path) if b.of(slot, game, villages) and b.heading.startswith("Villager ")]
        if found:
            return path, {b.identity: b for b in found}
    return None, {}


def is_population(path: Path) -> bool:
    return path.parent.name == "Tribe Population"


# ---------------------------------------------------------------------------
# Planning each kind
# ---------------------------------------------------------------------------

def _after_name(b: Block, upto: str) -> int:
    """The line a new line of rank `upto` follows: the last of Name, Custom title, Special
    villager that precedes it."""
    labels = {"custom": ("Name",), "special": ("Name", "Custom title"),
              "mask": ("Name", "Custom title", "Special villager")}[upto]
    at = b.index_of("Name")
    for label in labels:
        k = b.index_of(label)
        if k is not None:
            at = max(at, k)
    return at


def _from_date_question(key: str, who: str, what: str, dates: list[str]) -> Question:
    options = [f"From {d}" for d in dates] + [FROM_NOW]
    return Question(key, f"{who} has {what} now. From which Village History snapshot on should "
                         f"the older records show it?", options, FROM_NOW)


def _dated_inserts(kind: Kind, rank_name: str, label: str, value: str, key: str,
                   snapshots: list[Block]) -> None:
    """One insert per snapshot, decided by the from-date answer."""
    dates = []
    for b in sorted(snapshots, key=lambda b: b.date or ""):
        if b.date and b.date not in dates:
            dates.append(b.date)
    if not dates:
        return
    who = snapshots[0].value("Name")
    kind.questions[key] = _from_date_question(key, who, f"the {label.lower()} \"{value}\"", dates)
    for b in snapshots:
        answers = {f"From {d}": f"  {label}: {value}" for d in dates if b.date and b.date >= d}
        kind.inserts.append(Insert(b.path, _after_name(b, rank_name), RANK[rank_name],
                                   question=key, by_answer=answers))


AMBIGUOUS = object()


def _persons(current: dict) -> dict:
    """Each current villager by name, likes and dislikes; AMBIGUOUS when two share them."""
    out: dict = {}
    for identity, now in current.items():
        key = now.person
        if key is not None:
            out[key] = AMBIGUOUS if key in out else identity
    return out


def _now_of(b: Block, current: dict, persons: dict) -> tuple | None:
    """The current villager (an identity of `current`) a record is of: by identity, else by
    name, likes and dislikes when exactly one current villager has them."""
    if b.identity in current:
        return b.identity
    found = persons.get(b.person) if b.person is not None else None
    return found if found is not None and found is not AMBIGUOUS else None


def plan_custom_titles(folder: Path, slot: int, people: list[Block], current: dict) -> Kind:
    kind = Kind("custom", "Custom titles in older History snapshots")
    persons = _persons(current)
    for identity, now in current.items():
        title = now.value("Custom title")
        if not title:
            continue
        older = [b for b in people if _now_of(b, current, persons) == identity and b.date
                 and not is_population(b.path) and b.value("Custom title") is None]
        _dated_inserts(kind, "custom", "Custom title", title, f"custom|{identity}", older)
    return kind


def plan_masks(folder: Path, slot: int, people: list[Block], current: dict, page: Path | None) -> Kind:
    kind = Kind("mask", "Masks in older History snapshots")
    if not any(b.value("Mask") for b in current.values()):
        kind.notes.append("No villager wears a mask on the latest Village Population page. If some do, "
                          "play the village once with this patcher and save, then Repair Saves & Logs can add them.")
        return kind
    persons = _persons(current)
    for identity, now in current.items():
        mask = now.value("Mask")
        if not mask:
            continue
        older = [b for b in people if _now_of(b, current, persons) == identity and b.date
                 and not is_population(b.path) and b.value("Mask") is None]
        _dated_inserts(kind, "mask", "Mask", mask, f"mask|{identity}", older)
    return kind


def _skill_title(game: int, skills: list[int]) -> str | None:
    if game == 4 and len(skills) >= 5 and all(s >= 88 for s in skills[:5]):
        return "Scholar"
    if game in (3, 5) and sum(s >= 88 for s in skills) >= 3:
        return "Esteemed Elder"
    return None


def plan_special(folder: Path, game: int, slot: int, people: list[Block], current: dict) -> Kind:
    """The Special villager line.  Decided: a title the record's own skills give (Scholar, an
    Esteemed Elder in The Secret City and New Believers when the villager holds no other title
    now), a grave that names a title, a Golden Child (A New Home: from birth).  Asked: a title the
    villager holds now that the records cannot date (Tribal Chief, The Lost Children's Esteemed
    Elder, New Believers' Heathen roles and former Heathens)."""
    kind = Kind("special", "Special villager titles in older records")
    asked: dict[tuple, list[Block]] = {}
    persons = _persons(current)
    for b in people:
        if is_population(b.path) or b.value("Special villager") is not None or b.value("Name") is None:
            continue
        mine = _now_of(b, current, persons)
        now = current.get(mine) if mine is not None else None
        now_title = now.value("Special villager") if now is not None else None
        title = None
        if b.heading.startswith(("Death", "Disappeared")):
            grave = b.value("Grave")
            title = grave if grave in SPECIAL_TITLES else None
        elif game == 1 and now_title == "Golden Child":
            title = "Golden Child"
        elif now_title is not None and now_title != "Esteemed Elder" and game in (2, 3, 5):
            if b.date:
                asked.setdefault(mine, []).append(b)
            continue
        elif game == 2 and now_title == "Esteemed Elder":
            if b.date:
                asked.setdefault(mine, []).append(b)
            continue
        else:
            title = _skill_title(game, b.skills)
        if title:
            kind.inserts.append(Insert(b.path, _after_name(b, "special"), RANK["special"],
                                       line=f"  Special villager: {title}"))
    for identity, older in asked.items():
        title = current[identity].value("Special villager")
        _dated_inserts(kind, "special", "Special villager", title, f"special|{identity}", older)
    return kind


def plan_sex(folder: Path, game: int) -> Kind:
    """The Sex line: decided by the save, the logs or the game's name lists
    (scripts/vvfp_consistency_check.py missing_sex); a villager nothing records is asked."""
    checker = tools.load_checker()
    kind = Kind("sex", "Sex in older records")
    for path, adds in checker.missing_sex(folder, game):
        named = GAME_IN_NAME.search(path.name)
        if named and int(named.group(1)) != game:
            continue
        lines = read_lines(path)
        for after, line, _source in adds:
            if line:
                kind.inserts.append(Insert(path, after, 0, line=line))
                continue
            indent = "    " if lines[after].startswith("    ") or re.match(r"^  (Child|Mother|Father):", lines[after]) \
                else "  "
            name, head, body = _who_at(lines, after)
            key = f"sex|{name}|{head}|{body}"
            kind.questions.setdefault(key, Question(
                key, f"Is {name} male or female? (No save, record or name list says.)",
                ["Male", "Female", DONT_KNOW], DONT_KNOW))
            kind.inserts.append(Insert(path, after, 0, question=key,
                                       by_answer={"Male": f"{indent}Sex: Male", "Female": f"{indent}Sex: Female"}))
    return kind


def _who_at(lines: list[str], at: int) -> tuple:
    """(name, head, body) of the villager whose lines `at` is among."""
    name = head = body = None
    start = at
    label = "Name"
    for k in range(at, max(-1, at - 12), -1):
        m = re.match(r"^\s*(Name|Child|Mother|Father): (.*)$", lines[k])
        if m:
            label, name, start = m.group(1), m.group(2).strip(), k
            break
    # A record's own "Name:" has its Head and Body beside it; a Child / Mother / Father
    # (and a snapshot's "Parents:" Father / Mother) has them two spaces further in.
    own = re.match(r"^(\s*)", lines[start]).group(1)
    indent = own if label == "Name" else own + "  "
    for line in lines[start + 1:start + 14]:
        if not line.startswith(indent):
            break
        m = re.match(rf"^{indent}(Head|Body): (-?\d+)", line)
        if m and m.group(1) == "Head" and head is None:
            head = int(m.group(2))
        elif m and m.group(1) == "Body" and body is None:
            body = int(m.group(2))
    return name, head, body


def plan_born_as(folder: Path, game: int, slot: int) -> Kind:
    """Birth records' "Born as" line.  A delivery's Birth records are written together, one after
    another, with the mother's own lines; the Conception record before them says how many babies
    the pregnancy held.  When both agree it is decided; otherwise the player is asked."""
    checker = tools.load_checker()
    kind = Kind("born_as", "Twin / Triplet in older Birth records")
    words = {1: "Single birth", 2: "Twin", 3: "Triplet"}
    villages = current_villages(folder, game, slot)
    # Every layout the Birth records have had (native/shared/save_reset.c): an upgrade keeps the
    # older ones where they were until the game is next played (Codex, #553).
    paths = [path for root in (checker.LOGS, "VVFP Logs")
             for sub, words in (("Births and Conceptions", "Births and Conceptions Log"),
                                ("Tribe Parental Records", "Parentage Log"))
             for path in checker.numbered(folder / root / sub, f"Virtual Villagers {game} {words}")]
    for path in paths:
        lines = read_lines(path)
        all_blocks = [b for b in blocks(path, lines) if b.of(slot, game, villages)]
        last_babies: dict[tuple, int] = {}
        k = 0
        while k < len(all_blocks):
            b = all_blocks[k]
            if b.heading.startswith("Conception"):
                mother = _sub_identity(b, "Mother")
                babies = b.value("Babies in pregnancy")
                if mother and babies and babies.isdigit():
                    last_babies[mother] = int(babies)
                k += 1
                continue
            if b.heading != "Birth":
                k += 1
                continue
            mother = _sub_identity(b, "Mother")
            group = [b]
            while k + len(group) < len(all_blocks) and all_blocks[k + len(group)].heading == "Birth" \
                    and _sub_identity(all_blocks[k + len(group)], "Mother") == mother \
                    and len(group) < 3:
                group.append(all_blocks[k + len(group)])
            k += len(group)
            todo = [g for g in group if g.value("Born as") is None]
            if not todo:
                continue
            backfilled = any((g.value("Note") or "").startswith("Recorded afterwards") for g in group)
            expected = last_babies.pop(mother, None) if mother else None
            for g in todo:
                anchor = _birth_anchor(g)
                if expected is not None and expected == len(group) and not backfilled:
                    kind.inserts.append(Insert(path, anchor, 0, line=f"  Born as: {words[expected]}"))
                else:
                    key = f"born|{path.name}|{group[0].start}"
                    names = ", ".join(x.value("Child", "  ") or "?" for x in group)
                    kind.questions.setdefault(key, Question(
                        key, f"{mother[0] if mother else 'A mother'}'s baby/babies {names}: how many babies "
                             f"were born together?", ["Single birth", "Twin", "Triplet", DONT_KNOW], DONT_KNOW))
                    kind.inserts.append(Insert(path, anchor, 0, question=key,
                                               by_answer={w: f"  Born as: {w}" for w in words.values()}))
    return kind


def plan_golden(folder: Path, game: int, slot: int) -> Kind:
    """A New Home's Golden Child as a Birth.  The puzzle makes the Golden Child from a pregnant
    mother and ends her pregnancy, so it is a birth (the owner, 2026-10-08: "THE GOLDEN CHILD
    SHOULD BE LISTED AS A BIRTH WITH THEIR PARENTS LISTED" -- parents, age, skills, likes and
    dislikes).  An older patcher wrote it as an Arrived record with no parents.  The pregnancy
    it ended is a Conception with no Birth after it; the player picks which (the logs alone
    cannot tell), and a Birth record is added after the Arrived one, which is kept."""
    kind = Kind("golden", "The Golden Child as a Birth, with its parents")
    if game != 1:
        return kind
    checker = tools.load_checker()
    villages = current_villages(folder, game, slot)
    paths = [path for root in (checker.LOGS, "VVFP Logs")
             for sub, words in (("Births and Conceptions", "Births and Conceptions Log"),
                                ("Tribe Parental Records", "Parentage Log"))
             for path in checker.numbered(folder / root / sub, f"Virtual Villagers {game} {words}")]
    every: list[Block] = []
    for path in paths:
        every += [b for b in blocks(path) if b.of(slot, game, villages)]
    born = {b.value("Child", "  ") for b in every if b.heading == "Birth"}
    for k, b in enumerate(every):
        if not (b.heading.startswith("Arrived") and b.value("Special villager") == "Golden Child"):
            continue
        name = b.value("Name")
        if not name or name in born:
            continue
        # The pregnancies with no Birth after them, before this record, most recent first.
        open_: list[tuple[tuple, tuple]] = []
        for c in every[:k]:
            if c.heading.startswith("Conception"):
                mother, father = _sub_identity(c, "Mother"), _sub_identity(c, "Father")
                if mother and father:
                    open_ = [o for o in open_ if o[0] != mother] + [(mother, father)]
            elif c.heading == "Birth":
                mother = _sub_identity(c, "Mother")
                open_ = [o for o in open_ if o[0] != mother]
        if not open_:
            kind.notes.append(f"{name}, the Golden Child: no pregnancy in the logs could be theirs; nothing added.")
            continue
        choices = {f"{m[0]} and {f[0]}": (m, f) for m, f in reversed(open_)}
        key = f"golden|{b.path.name}|{b.start}"
        kind.questions[key] = Question(
            key, f"{name} is the Golden Child: whose pregnancy did the puzzle end? (mother and father)",
            list(choices) + [DONT_KNOW], DONT_KNOW)
        kind.inserts.append(Insert(b.path, b.start + len(b.lines) - 1, 9, question=key, by_answer={
            words: _golden_birth(b, m, f) for words, (m, f) in choices.items()}))
    return kind


def _golden_birth(arrived: Block, mother: tuple, father: tuple) -> str:
    """A Birth record, as the exporter writes one, for the Golden Child's Arrived record."""
    lines = ["", "Birth", f"  Child: {arrived.value('Name')}"]
    for label in ("Sex", "Head", "Body", "Likes", "Dislikes"):
        if arrived.value(label) is not None:
            lines.append(f"    {label}: {arrived.value(label)}")
    inside = False
    for line in arrived.lines:
        if line.startswith("  Skills:"):
            inside = True
            lines.append(line)
            continue
        if inside:
            if not line.startswith("    "):
                break
            lines.append(line)
    for label, (name, head, body) in (("Mother", mother), ("Father", father)):
        lines += [f"  {label}: {name}", f"    Head: {head}", f"    Body: {body}"]
    lines += ["  Born as: Golden Child", "  Age at birth: 100 (5 years old)",
              "  Note: Recorded afterwards (the Golden Child's parents, from the pregnancy the player chose)"]
    return "\n".join(lines)


def _sub_identity(b: Block, label: str) -> tuple | None:
    """(name, head, body) of a Birth / Conception record's Mother or Father section."""
    at = None
    for k, line in enumerate(b.lines):
        if line.startswith(f"  {label}:"):
            at = k
            break
    if at is None:
        return None
    name = b.lines[at].split(":", 1)[1].strip()
    head = body = None
    for line in b.lines[at + 1:]:
        if not line.startswith("    "):
            break
        m = re.match(r"^    (Head|Body): (-?\d+)", line)
        if m:
            if m.group(1) == "Head":
                head = int(m.group(2))
            else:
                body = int(m.group(2))
    return (name, head, body)


def _birth_anchor(b: Block) -> int:
    """The line a Birth record's "Born as" follows: the Father section's last line."""
    at = None
    for k, line in enumerate(b.lines):
        if line.startswith("  Father:"):
            at = k
            continue
        if at is not None and not line.startswith("    "):
            break
        if at is not None:
            at = k
    return b.start + (at if at is not None else len(b.lines) - 1)


LOOK_CAUSES = ("An island event", "A Custom Island Event", "The Change Appearance upgrade")


def plan_appearance(folder: Path, game: int, slot: int) -> Kind:
    """A villager whose look changed with no record of it (the tree's reader matched them by name,
    sex and recorded parents: vv_genealogy._unrecorded_looks): the player says how -- an island
    event, a Custom Island Event or the Change Appearance upgrade (the owner, 2026-10-08: "ask the
    player how a villager's appearance might have changed") -- and an "Appearance changed" record
    saying so is added at the end of the village's Births and Conceptions log, so the change is on
    record like one made today."""
    import vv_genealogy as gen
    kind = Kind("appearance", "Appearance changes with no record (how each happened)")
    checker = tools.load_checker()
    villages = current_villages(folder, game, slot)
    current = [path for path in checker.numbered(folder / checker.LOGS / "Births and Conceptions",
                                                 f"Virtual Villagers {game} Births and Conceptions Log")]
    # Every Births and Conceptions log the tree reads, older layouts too (Codex, #577: a record kept only in
    # a retired folder was missed, so Repair could offer it -- and add it -- again); the current ones last,
    # so a new record goes at the end of the current log.
    older = [path for path in checker.log_files(folder) if "Births and Conceptions" in path.name
             and path not in current and f"Virtual Villagers {game} " in path.name]
    paths = older + current
    every: list[Block] = []
    for path in paths:
        every += [b for b in blocks(path) if b.of(slot, game, villages)]
    if not every:
        return kind
    logged = set()
    for b in every:
        if b.heading == "Appearance changed":
            values = [b.value(label) for label in ("Name", "Old head", "Old body")]
            if all(values) and values[1].lstrip("-").isdigit() and values[2].lstrip("-").isdigit():
                logged.add((values[0], int(values[1]), int(values[2])))
    try:
        village = gen.load_village(folder, game, slot, full_names=False)
    except (gen.GenealogyError, OSError, ValueError):
        return kind
    last = every[-1]
    anchor = last.start + len(last.lines) - 1
    for old, new in sorted(village.relooked.items(), key=lambda item: str(item)):
        if old in logged or None in old or None in new:
            continue
        name, old_head, old_body = old
        _name, new_head, new_body = new
        key = f"look|{name}|{old_head}|{old_body}|{new_head}|{new_body}"
        kind.questions[key] = Question(
            key, f"{name}'s look changed from head {old_head}, body {old_body} to head {new_head}, body "
                 f"{new_body}, and nothing recorded it. How did it change?", [*LOOK_CAUSES, DONT_KNOW], DONT_KNOW)
        record = "\n".join(["", "Appearance changed", f"  Name: {name}", f"  Old head: {old_head}",
                            f"  Old body: {old_body}", f"  New head: {new_head}", f"  New body: {new_body}"])
        kind.inserts.append(Insert(last.path, anchor, len(kind.inserts), question=key, by_answer={
            cause: record + f"\n  Changed by: {cause[0].lower() + cause[1:]}"
                            "\n  Note: Recorded afterwards (how it happened, as the player said)"
            for cause in LOOK_CAUSES}))
    return kind


HEATHEN_ROLES = ("Heathen Doctor", "Heathen Chief", "Heathen Master Scientist", "Heathen Master Builder",
                 "Heathen Master Farmer", "Heathen Mommy")
CONVERTED = "Converted from the Heathens"
# A Birth record's heading: "Birth", or "Birth <n>" once every game numbers them (the shared
# reader is scripts/vvfp_consistency_check.py is_birth_heading on feat/numbered-births).
BIRTH_HEADING = re.compile(r"^Birth( \d+)?$")
# ...and the Arrived and Disappeared records' headings, numbered or not, the same way.
ARRIVED_HEADING = re.compile(r"^Arrived( \d+)?$")
DISAPPEARED_HEADING = re.compile(r"^Disappeared( \d+)?$")
LEFT_FOR_THE_HEATHENS = "Left the tribe: became a Heathen"


def _faction_of_title(title: str | None) -> str | None:
    """What a record's own Special villager line says of its faction then: a Heathen role title is
    only ever a current Heathen's, a former Heathen's titles only a believer's
    (native/shared/special_title.h)."""
    if title in HEATHEN_ROLES:
        return "Heathen"
    if title and (title.startswith("Former Heathen") or title == "Retired Heathen Chief"):
        return "Believer"
    return None


def _faction_events(folder: Path, game: int, slot: int) -> tuple[set, set, set]:
    """Who the logs say converted from the Heathens (Arrived "How: Converted from the Heathens"),
    left for the Heathens (Disappeared "Left the tribe: became a Heathen"), and came as a believer
    (a Birth's child, any other Arrived record): sets of (name, head, body)."""
    checker = tools.load_checker()
    converted, left, believer = set(), set(), set()
    villages = current_villages(folder, game, slot)
    for path in checker.log_files(folder):
        for b in blocks(path):
            if not b.of(slot, game, villages):
                continue
            if ARRIVED_HEADING.match(b.heading):
                (converted if b.value("How") == CONVERTED else believer).add(b.identity)
            elif DISAPPEARED_HEADING.match(b.heading) and b.value("What happened") == LEFT_FOR_THE_HEATHENS:
                left.add(b.identity)
            elif BIRTH_HEADING.match(b.heading):
                child = _sub_identity(b, "Child")
                if child:
                    believer.add(child)
    return converted, left, believer


def plan_faction(folder: Path, game: int, slot: int, people: list[Block], current: dict) -> Kind:
    """New Believers' Faction line ("Faction: Heathen" / "Faction: Believer", as
    native/population_export/population_export.c writes it) in older Village History and Village
    Population records.  Decided: the record's own Special villager title (a Heathen role, or a
    former Heathen's title), and a villager whose faction the latest Village Population page gives
    and whom no record shows changing sides (never converted, never left for the Heathens; a
    Heathen now who never came as a believer).  Asked: everyone else -- a faction change the logs
    cannot date, or a villager no longer in the village."""
    kind = Kind("faction", "Faction (Heathen or Believer) in older New Believers records")
    if game != 5:
        return kind
    converted, left, believer = _faction_events(folder, game, slot)
    persons = _persons(current)
    asked: dict[tuple, list[Block]] = {}
    for b in people:
        if not b.heading.startswith("Villager ") or b.value("Faction") is not None or b.value("Name") is None:
            continue
        own = _faction_of_title(b.value("Special villager"))
        mine = _now_of(b, current, persons)
        now = current.get(mine).value("Faction") if mine is not None else None
        who = mine if mine is not None else b.identity
        changed = who in converted or who in left or b.identity in converted or b.identity in left
        value = own
        if value is None and now is not None and not changed:
            if now == "Believer" or (who not in believer and b.identity not in believer):
                value = now
        if value is None:
            asked.setdefault(who, []).append(b)
            continue
        kind.inserts.append(Insert(b.path, _faction_after(b), RANK_FACTION, line=f"  Faction: {value}"))
    for who, older in asked.items():
        dates = sorted({b.date for b in older if b.date})
        name = older[0].value("Name")
        options = ["Believer in every one of them", "Heathen in every one of them"]
        options += [f"Heathen from {d}, a believer before" for d in dates[1:]]
        options += [f"Believer from {d}, a Heathen before" for d in dates[1:]]
        options.append(DONT_KNOW)
        key = f"faction|{who}"
        kind.questions[key] = Question(
            key, f"Was {name} a Heathen or a believer in the older Village History and Village Population "
                 f"records? (No record settles it.)", options, DONT_KNOW)
        for b in older:
            answers = {"Believer in every one of them": "  Faction: Believer",
                       "Heathen in every one of them": "  Faction: Heathen"}
            for d in dates[1:]:
                before = bool(b.date) and b.date < d
                answers[f"Heathen from {d}, a believer before"] = f"  Faction: {'Believer' if before else 'Heathen'}"
                answers[f"Believer from {d}, a Heathen before"] = f"  Faction: {'Heathen' if before else 'Believer'}"
            kind.inserts.append(Insert(b.path, _faction_after(b), RANK_FACTION, question=key, by_answer=answers))
    return kind


# After the Sex line (and the Sex line an older record is given, rank 0, first).
RANK_FACTION = 5


def _faction_after(b: Block) -> int:
    for label in ("Sex", "Age"):
        k = b.index_of(label)
        if k is not None:
            return k
    return _after_name(b, "mask")


def plan(folder: Path, game: int, slot: int) -> list[Kind]:
    """Everything older records of this slot's village lack, kind by kind.  Reads only."""
    folder = Path(folder)
    people = person_blocks(folder, slot, game)
    page, current = population_page(folder, slot, game)
    kinds = [
        plan_sex(folder, game),
        plan_special(folder, game, slot, people, current),
        plan_custom_titles(folder, slot, people, current),
        plan_masks(folder, slot, people, current, page),
        plan_born_as(folder, game, slot),
        plan_golden(folder, game, slot),
        plan_appearance(folder, game, slot),
        plan_faction(folder, game, slot, people, current),
    ]
    return kinds


# ---------------------------------------------------------------------------
# Applying
# ---------------------------------------------------------------------------

def resolve(kinds: list[Kind], chosen: set[str],
            answers: dict[str, str]) -> dict[Path, list[tuple[int, int, str, str]]]:
    """The lines to add, per file: (after, rank, line, kind id), for the ticked kinds and the
    answers given."""
    out: dict[Path, list[tuple[int, int, str, str]]] = {}
    for kind in kinds:
        if kind.id not in chosen:
            continue
        for ins in kind.inserts:
            line = ins.line
            if line is None and ins.question is not None:
                line = ins.by_answer.get(answers.get(ins.question, ""))
            if line:
                out.setdefault(ins.path, []).append((ins.after, ins.rank, line, kind.id))
    return out


def apply(folder: Path, kinds: list[Kind], chosen: set[str],
          answers: dict[str, str]) -> dict[str, list[tools.WordFix]]:
    """Add the chosen kinds' lines, every file in one pass (the plan's line numbers are the
    file's as read).  Each file is copied first, into Data\\Copies Made Before Repairs (never
    replacing a copy), and
    rewritten through a temporary file.  Returns, per kind, the files it added lines to."""
    folder = Path(folder)
    done: dict[str, list[tools.WordFix]] = {}
    written = 0
    for path, adds in resolve(kinds, chosen, answers).items():
        adds = sorted(set(adds), key=lambda a: (a[0], a[1]))
        raw = path.read_bytes()
        crlf = b"\r\n" in raw
        lines = raw.decode("latin-1").replace("\r\n", "\n").split("\n")
        # Highest line first; at one line, the highest rank first, so ranks read in order.
        for after, _rank, line, _kind in reversed(adds):
            lines.insert(after + 1, line)
        text = "\n".join(lines)
        if crlf:
            text = text.replace("\n", "\r\n")
        backup = tools._word_backup(folder, path)
        temporary = path.with_name(path.name + ".tmp")
        try:
            with open(path, "rb") as source, open(backup, "xb") as copy:
                copy.write(source.read())
            temporary.write_bytes(text.encode("latin-1"))
            os.replace(temporary, path)
        except OSError as exc:
            try:
                temporary.unlink()
            except OSError:
                pass
            raise tools.LogToolError(f"{path.name} could not be given its added lines ({exc}). "
                                     f"{written} log file(s) were given them before it.") from exc
        written += 1
        for kind_id in sorted({a[3] for a in adds}):
            count = sum(1 for a in adds if a[3] == kind_id)
            done.setdefault(kind_id, []).append(tools.WordFix(str(path.relative_to(folder)), count, backup.name))
    return done
