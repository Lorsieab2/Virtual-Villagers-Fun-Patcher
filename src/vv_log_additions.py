"""Repair Logs: what older log records lack, and adding it (all five games).

The owner (2026-10-06): Check Logs and Repair Logs ask the player whether to
add, retroactively, what records written by an older patcher lack -- the Sex
line, the Special villager title, the Custom title, the Mask, Twin / Triplet
-- and "CHECK ALL SAVES, DAT FILES AND EXES. IF EVER UNSURE, ASK THE PLAYER".

So every kind is planned from what the save, the patcher's own files and the
logs themselves settle, and whatever they cannot settle becomes a Question the
player answers in the Repair Logs window; an unanswered question ("Don't
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
}
ADDED = {"sex": "Sex added", "special": "Special villager added", "custom": "Custom title added",
         "mask": "Mask added", "born_as": "Born as added"}
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

    def of(self, slot: int, game: int) -> bool:
        """Under this slot's village of this game (Codex, #553: two games may share a folder)."""
        return self.slot == slot and (self.game is None or self.game == game)

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
    slot = date = None
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
                offset += 1
            if offset < len(chunk):
                out.append(Block(path, start + offset, chunk[offset:], slot, date, game))
            start = None
    return out


def person_blocks(folder: Path, slot: int, game: int) -> list[Block]:
    """Every one-villager record (History / Population snapshot entries, Deaths, Disappeared,
    Arrived, Unaccounted) under this slot's village, in every log."""
    checker = tools.load_checker()
    out = []
    for path in checker.log_files(folder):
        for b in blocks(path):
            if b.of(slot, game) and PERSON_HEAD.match(b.heading):
                out.append(b)
    return out


def population_page(folder: Path, slot: int, game: int) -> tuple[Path | None, dict[tuple, Block]]:
    """The slot's latest Village Population page: each living villager by (name, head, body)."""
    checker = tools.load_checker()
    for path in checker.numbered(folder / checker.LOGS / "Tribe Population", "Village Population"):
        found = [b for b in blocks(path) if b.of(slot, game) and b.heading.startswith("Villager ")]
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


def plan_custom_titles(folder: Path, slot: int, people: list[Block], current: dict) -> Kind:
    kind = Kind("custom", "Custom titles in older History snapshots")
    for identity, now in current.items():
        title = now.value("Custom title")
        if not title:
            continue
        older = [b for b in people if b.identity == identity and b.date and not is_population(b.path)
                 and b.value("Custom title") is None]
        _dated_inserts(kind, "custom", "Custom title", title, f"custom|{identity}", older)
    return kind


def plan_masks(folder: Path, slot: int, people: list[Block], current: dict, page: Path | None) -> Kind:
    kind = Kind("mask", "Masks in older History snapshots")
    if not any(b.value("Mask") for b in current.values()):
        kind.notes.append("No villager wears a mask on the latest Village Population page. If some do, "
                          "play the village once with this patcher and save, then Repair Logs can add them.")
        return kind
    for identity, now in current.items():
        mask = now.value("Mask")
        if not mask:
            continue
        older = [b for b in people if b.identity == identity and b.date and not is_population(b.path)
                 and b.value("Mask") is None]
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
    for b in people:
        if is_population(b.path) or b.value("Special villager") is not None or b.value("Name") is None:
            continue
        now = current.get(b.identity)
        now_title = now.value("Special villager") if now is not None else None
        title = None
        if b.heading.startswith(("Death", "Disappeared")):
            grave = b.value("Grave")
            title = grave if grave in SPECIAL_TITLES else None
        elif game == 1 and now_title == "Golden Child":
            title = "Golden Child"
        elif now_title is not None and now_title != "Esteemed Elder" and game in (2, 3, 5):
            if b.date:
                asked.setdefault(b.identity, []).append(b)
            continue
        elif game == 2 and now_title == "Esteemed Elder":
            if b.date:
                asked.setdefault(b.identity, []).append(b)
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
    for path in checker.numbered(folder / checker.LOGS / "Births and Conceptions",
                                 f"Virtual Villagers {game} Births and Conceptions Log"):
        lines = read_lines(path)
        all_blocks = [b for b in blocks(path, lines) if b.of(slot, game)]
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
    file's as read).  Each file is copied beside itself first (never replacing a copy) and
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
        backup = tools._word_backup(path)
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
