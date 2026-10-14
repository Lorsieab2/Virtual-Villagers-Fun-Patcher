"""Repair Saves & Logs: remove a restarted tribe's villagers from the history (all five games, v1.35.73).

The owner (v1.35.73): "please implement this history revision in Repair logs for .73, with player
confirmation, to account for the player starting the game over with the same tribe name. yes, I confirm
2" -- option 2: remove ONLY the villagers PROVEN gone, and list the rest for the player to decide.  This
is the one exception to "history logs are never deleted", granted for a tribe started over under the
same name: its villagers' records sit under the very same "Village: <name> (Save <n>)" header as the
tribe being played now.  The owner: "several villagers are still present but renamed" -- so a name is
never proof of anything.

THE PROOF OF GONE.  A villager the logs name is removed only when ALL of this holds:

  * no villager in the save now is them: not by name, head and body; not by (a) identity -- the same sex,
    head, body, likes and dislikes, and not younger than any age the logs give them (a villager renamed
    since: the owner's Lupa Tangaroa is Coral Tangaroa now, Tamil Makawee is Mahalo Makawee); not by the
    same sex, head and body alone (likes and dislikes change: island events); and not by the same sex and
    one of head or body (a look changed as well);
  * (b) no Name changed or Appearance changed record, and no Island Events line that changes a name, a
    head or a body, names them;
  * (c) no villager in the save has their name (renamed in place, or the looks changed);
  * the game's own older copies of the save (<save>21.ldw, <save>41.ldw) do not hold them;
  * every Village History snapshot (or Village Population page) that lists them lists NO villager of the
    tribe being played -- the tribe being played is every snapshot that lists one of its villagers, and
    every snapshot that shares a villager with one of those, or is joined to one by a Birth record (so
    this tribe's own dead are never taken: they lived beside the living);
  * and those snapshots are all older than the first snapshot of the tribe being played (a tribe started
    over came first; anything else -- a restored backup -- is not proven).

Anything else is KEPT and listed with the reason ("still in the save under another name, or unproven").
When in doubt: keep and list.

WHAT IS REMOVED, for each villager proven gone: their Village History snapshot entries (and a snapshot's
heading when none of its villagers is left), their entries on an older Village Population page, their
Death, Disappeared, Left the tribe, Unaccounted and Arrived records, a Birth record whose child is gone
and whose parents are gone or unknown, a Conception whose mother is gone and whose father is gone or
unknown, and an Island Events record that names them by a name no other villager has.  The Village
Statistics logs name no villager in any game, so nothing there changes.  Never a villager in the save, the
save itself (.ldw), the Custom Titles file or any game data.  Record numbers are left as they are: the
game numbers each new record after the highest number in its files (native/parentage_export
count_running_records, family_number_floor), so a gap never makes a number repeat.

HOW.  The game must be closed.  Each log changed is copied first into "Virtual Villagers Fun Patcher
Data\\Copies Made Before Repairs" as "<name>.before-history-revision" (never replacing a copy), rewritten
through a temporary file moved into place, and read back; if any write fails, every file already
rewritten is put back from its copy.  The Like and Dislike Words boundaries move with the bytes taken
(src/vv_log_tools.py move_word_boundary).  The Repairs log gets one line per villager removed (name, sex,
head, body, the logs and the snapshot dates).
"""
from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import vv_log_tools as tools

KIND_ID = "history_revision"
LABEL = ("Remove villagers from the history that are not in this save (a restarted tribe with the same "
         "name)")
DEFAULT_TICKED = False          # the owner: the player must tick it and confirm
BACKUP_SUFFIX = ".before-history-revision"
CHECKED = ("the villagers the logs list that are not in this save (a tribe started over with the same name): "
           "removed only when proven gone -- no villager in the save, no older copy of the save, no Name "
           "changed, Appearance changed or Island Events record and no shared name ties them to this tribe, "
           "and only snapshots older than this tribe's own list them")
CORRECTED = "Removed"

PERSON = re.compile(r"^(Villager \d+|Death \d+|Disappeared(?: \d+)?|Left the tribe|Unaccounted \d+|Arrived \d+)\s*$")
DEPARTED = re.compile(r"^(Death \d+|Disappeared(?: \d+)?|Left the tribe|Unaccounted \d+)\s*$")
ARRIVED = re.compile(r"^Arrived \d+\s*$")
BIRTH = re.compile(r"^Birth(?: \d+)?\s*$")
CONCEPTION = re.compile(r"^Conception \d+\s*$")
EVENT = re.compile(r"^Island event \d+\s*$")
SNAPSHOT = re.compile(r"^=== Virtual Villagers (\d)\b.* -- (.*) ===\s*$")
VILLAGE = re.compile(r"^Village: .*\(Save (\d)\)\s*$")


class HistoryRevisionError(tools.LogToolError):
    """Nothing was changed (or everything changed was put back); the message says why."""


# ---------------------------------------------------------------------------
# What the logs say
# ---------------------------------------------------------------------------

@dataclass
class Person:
    """One villager the logs name, by name, head and body."""
    name: str
    head: int | None
    body: int | None
    sexes: set = field(default_factory=set)
    ages: list = field(default_factory=list)
    likes: list = field(default_factory=list)         # each record's frozenset (None: not said)
    dislikes: list = field(default_factory=list)
    censuses: set = field(default_factory=set)        # census ids that list them
    places: list = field(default_factory=list)        # (path, line, heading)

    @property
    def key(self) -> tuple:
        return (self.name, self.head, self.body)

    @property
    def sex(self) -> str | None:
        return next(iter(self.sexes)) if len(self.sexes) == 1 else None

    @property
    def youngest(self) -> int | None:
        return min(self.ages) if self.ages else None

    def described(self) -> str:
        sex = f"{self.sex}, " if self.sex else ""
        return f"{self.name} ({sex}head {self.head}, body {self.body})"


@dataclass
class Census:
    """One Village History snapshot, or one Village Population page."""
    id: int
    path: Path
    when: str                   # "YYYY-MM-DD HH:MM:SS" ("" for a Population page: its file's time)
    label: str
    keys: list = field(default_factory=list)
    heading: tuple | None = None    # (start, count) of a snapshot's "=== ... ===" / "Village:" lines
    entries: list = field(default_factory=list)       # (start, count, key)


@dataclass
class Verdict:
    person: Person
    gone: bool
    reason: str


@dataclass
class Cut:
    """Lines to take out of one log: a record, or a snapshot's heading."""
    path: Path
    start: int
    count: int
    what: str                   # its heading
    who: tuple | None           # the gone villager's key (None: a snapshot heading)
    when: str | None = None     # the snapshot's date


@dataclass
class Plan:
    folder: Path
    game: int
    slot: int
    village: str | None
    gone: list[Verdict]
    kept: list[Verdict]
    cuts: list[Cut]
    notes: list[str] = field(default_factory=list)

    @property
    def gone_keys(self) -> set:
        return {v.person.key for v in self.gone}

    def files(self) -> dict[Path, list[Cut]]:
        out: dict[Path, list[Cut]] = {}
        for cut in self.cuts:
            out.setdefault(cut.path, []).append(cut)
        return out

    def describe(self) -> str:
        """The confirmation's text: per log, the blocks removed with a count; then who is kept and why."""
        rel = lambda p: _rel(self.folder, p)                    # noqa: E731
        out = [f"{self.village or 'This village'}: {len(self.gone)} villager(s) proven gone would be removed "
               f"from the logs; {len(self.kept)} villager(s) not in the save are kept."]
        if self.cuts:
            out.append("")
            out.append("Removed (a copy of each log is made first):")
            for path, cuts in self.files().items():
                records = [c for c in cuts if c.who is not None]
                headings = len(cuts) - len(records)
                more = f" and {headings} emptied snapshot heading(s)" if headings else ""
                out.append(f"  {rel(path)}: {len(records)} block(s){more}")
                for c in records:
                    when = f" (snapshot {c.when})" if c.when else ""
                    out.append(f"    - {c.what}{when}: {_who(c.who)}")
        if self.gone:
            out.append("")
            out.append("Villagers removed:")
            for v in self.gone:
                out.append(f"  - {v.person.described()}: {v.reason}")
        if self.kept:
            out.append("")
            out.append("Kept (still in the save under another name, or unproven):")
            for v in self.kept:
                out.append(f"  - {v.person.described()}: {v.reason}")
        out += [""] + self.notes if self.notes else []
        return "\n".join(out)


def _who(key: tuple | None) -> str:
    if key is None:
        return "(heading)"
    name, head, body = key
    return f"{name} (head {head}, body {body})"


def _rel(folder: Path, path: Path) -> str:
    try:
        return str(Path(path).relative_to(folder))
    except ValueError:
        return str(path)


def _words(value: str | None) -> frozenset | None:
    import vv_reconcile
    return vv_reconcile._words(value)


def _int(value: str | None) -> int | None:
    import vv_reconcile
    return vv_reconcile._int(value)


def _prefs_ok(person: Person, likes: frozenset | None, dislikes: frozenset | None) -> bool:
    """Some record of `person` lists likes and dislikes that may be these (a one-word older record is one
    of a longer list; a record that does not say agrees with anything)."""
    import vv_reconcile
    ok = vv_reconcile._compatible
    pairs = list(zip(person.likes, person.dislikes)) or [(None, None)]
    return any(ok(l, likes) and ok(d, dislikes) for l, d in pairs)


def _age_ok(person: Person, age: int | None) -> bool:
    """A villager in the save now is not younger than any age the logs give `person`."""
    return age is None or person.youngest is None or age >= person.youngest


def _sex_ok(person: Person, sex: str | None) -> bool:
    return not person.sexes or sex is None or sex in person.sexes


def _sub(lines: list[str], label: str) -> tuple | None:
    """A Birth or Conception record's "  Child:" / "  Mother:" / "  Father:" as (name, head, body), with
    the sex, likes, dislikes and age at conception under it."""
    for k, line in enumerate(lines):
        if line.startswith(f"  {label}:"):
            name = line.split(":", 1)[1].strip()
            if not name or name.startswith("("):
                return None
            values: dict[str, str] = {}
            for sub in lines[k + 1:]:
                if not sub.startswith("    "):
                    break
                if ":" in sub:
                    key, value = sub.strip().split(":", 1)
                    values.setdefault(key, value.strip())
            return (name, _int(values.get("Head")), _int(values.get("Body")), values)
    return None


def _value(lines: list[str], label: str) -> str | None:
    for line in lines:
        if line.startswith(f"  {label}:"):
            return line.split(":", 1)[1].strip()
    return None


def _record_span(lines: list[str], start: int, length: int) -> int:
    """A record's lines and the blank line after it."""
    end = start + length
    return length + (1 if end < len(lines) and not lines[end].strip() else 0)


# ---------------------------------------------------------------------------
# Planning (reads only)
# ---------------------------------------------------------------------------

def _current(folder: Path, game: int, slot: int):
    """(the living in the save now, everyone in the game's older copies of the save)."""
    import vv_reconcile
    checker = tools.load_checker()
    save = Path(folder) / f"{checker.SAVE_STEMS[game]}{slot}.ldw"
    if not save.is_file():
        raise HistoryRevisionError(f"Save {slot} has no tribe ({save.name} is not there).")
    try:
        living, _bodies = vv_reconcile.read_save(save, game)
    except (vv_reconcile.ReconcileError, OSError) as exc:
        raise HistoryRevisionError(f"The save could not be read, so nothing is offered ({exc}).") from exc
    older = []
    for path in vv_reconcile.save_generations(folder, game, slot)[:-1]:
        try:
            alive, bodies = vv_reconcile.read_save(path, game)
        except (vv_reconcile.ReconcileError, OSError):
            continue                        # an unreadable older copy only proves nothing
        older += [(path, s) for s in alive + bodies]
    return living, older


def plan(folder: Path, game: int, slot: int) -> Plan:
    """Who the logs of this slot's village name that is not in the save, each kept or proven gone, and
    the lines that would be taken out.  Reads only."""
    import vv_log_additions as additions
    folder = Path(folder)
    checker = tools.load_checker()
    living, older = _current(folder, game, slot)
    villages = additions.current_villages(folder, game, slot)
    village = sorted(villages)[0] if villages and len(villages) == 1 else None

    people: dict[tuple, Person] = {}
    censuses: list[Census] = []
    records: list[tuple] = []           # (kind, path, start, count, heading, extra)
    linked: dict[str, str] = {}         # name -> the record that ties it to a change
    births_links: list[tuple] = []      # (child key, mother key, father key)
    lines_of: dict[Path, list[str]] = {}

    def person(name, head, body) -> Person:
        key = (name, head, body)
        if key not in people:
            people[key] = Person(name, head, body)
        return people[key]

    def note_person(p: Person, sex, age, likes, dislikes, path, start, heading) -> None:
        if sex:
            p.sexes.add(sex)
        if age is not None:
            p.ages.append(age)
        if likes is not None or dislikes is not None:
            p.likes.append(likes)
            p.dislikes.append(dislikes)
        p.places.append((path, start, heading))

    for path in checker.log_files(folder):
        try:
            lines = additions.read_lines(path)
        except OSError as exc:
            raise HistoryRevisionError(f"{path.name} could not be read ({exc}); nothing is offered.") from exc
        lines_of[path] = lines
        population = additions.is_population(path)
        page: Census | None = None
        snapshots: dict[int, Census] = {}
        # A snapshot's heading lines ("=== ... ===" and "Village: ..."), by the line they start at.
        for i, line in enumerate(lines):
            m = SNAPSHOT.match(line)
            if m and int(m.group(1)) == game and i + 1 < len(lines) and VILLAGE.match(lines[i + 1]) \
                    and lines[i + 1].rstrip() in (villages or {lines[i + 1].rstrip()}) \
                    and int(VILLAGE.match(lines[i + 1]).group(1)) == slot:
                count = 2
                while i + count < len(lines) and not lines[i + count].strip():
                    count += 1
                snapshots[i] = Census(len(censuses) + len(snapshots), path, m.group(2).strip(),
                                      f"the Village History snapshot of {m.group(2).strip()}", heading=(i, count))
        for c in sorted(snapshots.values(), key=lambda c: c.heading[0]):
            c.id = len(censuses)
            censuses.append(c)
        heads = sorted(snapshots)
        for b in additions.blocks(path, lines):
            if not b.of(slot, game, villages):
                continue
            head = b.heading
            count = _record_span(lines, b.start, len(b.lines))
            if head.startswith("Villager ") and (population or b.date):
                if population:
                    if page is None:
                        page = Census(len(censuses), path, "", f"the Village Population page ({path.name})")
                        censuses.append(page)
                    census = page
                else:
                    above = [h for h in heads if h < b.start]
                    if not above:
                        continue
                    census = snapshots[above[-1]]
                p = person(b.value("Name") or "", b.int_value("Head"), b.int_value("Body"))
                note_person(p, b.value("Sex"), b.int_value("Age"), _words(b.value("Likes")),
                            _words(b.value("Dislikes")), path, b.start, head)
                p.censuses.add(census.id)
                census.keys.append(p.key)
                census.entries.append((b.start, count, p.key))
            elif PERSON.match(head):
                p = person(b.value("Name") or "", b.int_value("Head"), b.int_value("Body"))
                age = (_int(b.value("Age at death")) if DEPARTED.match(head)
                       else _int(b.value("Age at arrival")) if b.value("Age at arrival") not in (None, "(unknown)")
                       else _int(b.value("Age when recorded")) if ARRIVED.match(head) else _int(b.value("Age")))
                note_person(p, b.value("Sex"), None if DEPARTED.match(head) else age,
                            _words(b.value("Likes")), _words(b.value("Dislikes")), path, b.start, head)
                records.append(("person", path, b.start, count, head, p.key))
            elif BIRTH.match(head):
                child, mother, father = _sub(b.lines, "Child"), _sub(b.lines, "Mother"), _sub(b.lines, "Father")
                if child is not None:
                    p = person(*child[:3])
                    v = child[3]
                    note_person(p, v.get("Sex"), None, _words(v.get("Likes")), _words(v.get("Dislikes")),
                                path, b.start, head)
                births_links.append((child[:3] if child else None, mother[:3] if mother else None,
                                     father[:3] if father else None))
                records.append(("birth", path, b.start, count, head,
                                (child[:3] if child else None, mother[:3] if mother else None,
                                 father[:3] if father else None)))
            elif CONCEPTION.match(head):
                mother, father = _sub(b.lines, "Mother"), _sub(b.lines, "Father")
                births_links.append((None, mother[:3] if mother else None, father[:3] if father else None))
                records.append(("conception", path, b.start, count, head,
                                (mother[:3] if mother else None, father[:3] if father else None)))
            elif head == "Name changed":
                for label in ("Name", "Old name"):
                    if b.value(label):
                        linked.setdefault(b.value(label), f"a Name changed record ({b.value('Old name')} -> "
                                                          f"{b.value('Name')})")
            elif head == "Appearance changed":
                if b.value("Name"):
                    linked.setdefault(b.value("Name"), f"an Appearance changed record names {b.value('Name')}")
            elif EVENT.match(head):
                name = b.value("Name") or ""
                changed = re.match(r"^\s*(.*?) -> (.*?)\s*$", name)
                if changed:
                    for n in changed.groups():
                        linked.setdefault(n, f"{head} in the Island Events log changes the name {name}")
                    records.append(("event", path, b.start, count, head, None))
                    continue
                if name and any(re.match(r"^  (Head|Body|Sex): .* -> ", line) for line in b.lines):
                    linked.setdefault(name, f"{head} in the Island Events log changes {name}'s looks")
                records.append(("event", path, b.start, count, head, name or None))

    # -- the tribe being played: every census that lists one of its villagers, and every census joined to
    # one by a shared villager or a Birth record.
    living_keys = {s.key for s in living}

    def strong(p: Person):
        """The villager in the save `p` is: by name, head and body, or by identity (renamed)."""
        exact = [s for s in living if s.key == p.key and _sex_ok(p, s.sex)]
        if exact:
            return exact[0], "is in the save now"
        same = [s for s in living if s.head == p.head and s.body == p.body and _sex_ok(p, s.sex)
                and _prefs_ok(p, s.likes, s.dislikes) and _age_ok(p, s.age)]
        if same:
            s = same[0]
            return s, (f"renamed: in the save now as {s.name} -- the same sex, head, body, likes and dislikes, "
                       "and not younger")
        return None

    lineage: set[int] = set()
    for p in people.values():
        if strong(p) is not None:
            lineage |= p.censuses
    joined: dict[int, set[int]] = {c.id: set() for c in censuses}
    for p in people.values():
        for a in p.censuses:
            joined[a] |= p.censuses
    for child, mother, father in births_links:
        ids = set()
        for key in (child, mother, father):
            if key is not None and key in people:
                ids |= people[key].censuses
        for a in ids:
            joined[a] |= ids
    grew = True
    while grew:
        grew = False
        for cid in list(lineage):
            more = joined.get(cid, set()) - lineage
            if more:
                lineage |= more
                grew = True
    by_id = {c.id: c for c in censuses}
    tribe_dates = sorted(by_id[c].when for c in lineage if by_id[c].when)
    first = tribe_dates[0] if tribe_dates else None

    gone: list[Verdict] = []
    kept: list[Verdict] = []
    notes: list[str] = []
    if not lineage:
        notes.append("No Village History snapshot lists a villager of the save, so which tribe each snapshot "
                     "is cannot be told: nothing is proven gone.")
    for p in sorted(people.values(), key=lambda p: (p.name, p.head or 0, p.body or 0)):
        if p.key in living_keys:
            continue                                    # in the save now: never listed, never removed
        found = strong(p)
        reason = None
        if found is not None:
            reason = found[1]
        if reason is None:
            looks = [s for s in living if s.head == p.head and s.body == p.body and _sex_ok(p, s.sex)
                     and _age_ok(p, s.age)]
            if looks:
                reason = (f"may be {looks[0].name}: the same sex, head and body (likes or dislikes may have "
                          "changed since)")
        if reason is None:
            named = [s for s in living if s.name == p.name]
            if named:
                s = named[0]
                reason = (f"shares the name {p.name} with a villager in the save ({s.looks()}): may be them, "
                          "renamed in place or with a changed look")
        if reason is None and p.name in linked:
            reason = f"{linked[p.name]}, which may tie them to a villager in the save"
        if reason is None:
            copies = [path.name for path, s in older
                      if (s.key == p.key or (s.head == p.head and s.body == p.body and _sex_ok(p, s.sex)))]
            if copies:
                reason = f"an older copy of the save ({copies[0]}) holds them"
        if reason is None:
            partly = [s for s in living if (s.head == p.head or s.body == p.body) and _sex_ok(p, s.sex)
                      and _age_ok(p, s.age) and _prefs_ok(p, s.likes, s.dislikes)]
            if partly:
                reason = (f"may be {partly[0].name} with a changed head or body: the same sex, likes and "
                          "dislikes and one of head or body")
        if reason is None and p.censuses & lineage:
            c = by_id[min(p.censuses & lineage)]
            reason = f"lived in this tribe: {c.label} also lists villagers of the save (or their family)"
        if reason is None and not p.censuses:
            reason = "no Village History snapshot places them in a tribe"
        if reason is None and not lineage:
            reason = "no snapshot of this tribe to tell the tribes apart"
        if reason is None:
            dates = sorted(by_id[c].when or by_id[c].label for c in p.censuses)
            if first is not None and any(d >= first for d in dates):
                reason = (f"listed in a snapshot dated {max(dates)}, after this tribe's first snapshot "
                          f"({first}): not proven to be a tribe started over before this one")
        if reason is not None:
            kept.append(Verdict(p, False, reason))
            continue
        dates = sorted(by_id[c].when for c in p.censuses if by_id[c].when)
        gone.append(Verdict(p, True,
                            "listed only in " + (f"the snapshot(s) of {', '.join(dates)}" if dates else "older pages")
                            + ", which list no villager of the save; nothing ties them to a villager in the save"))

    # -- the lines that go
    gone_keys = {v.person.key for v in gone}
    kept_names = ({s.name for s in living} | {v.person.name for v in kept}
                  | {p.name for p in people.values() if p.key not in gone_keys})
    cuts: list[Cut] = []
    for c in censuses:
        if c.id in lineage:
            continue
        mine = [(start, count, key) for start, count, key in c.entries if key in gone_keys]
        whole = c.heading is not None and mine and len(mine) == len(c.entries)
        lines = lines_of[c.path]
        for n, (start, count, key) in enumerate(mine):
            if whole and n == len(mine) - 1:
                # The whole snapshot goes: its last villager takes every blank line after it too (the
                # blank line that parts it from the next snapshot).
                while start + count < len(lines) - 1 and not lines[start + count].strip():
                    count += 1
            cuts.append(Cut(c.path, start, count, lines[start].strip(), key, c.when or None))
        if whole:
            start, count = c.heading
            cuts.append(Cut(c.path, start, count, lines[start].strip(), None, c.when))
    for kind, path, start, count, head, extra in records:
        if kind == "person":
            if extra in gone_keys:
                cuts.append(Cut(path, start, count, head, extra))
        elif kind == "birth":
            child, mother, father = extra
            if child in gone_keys and all(k is None or k in gone_keys for k in (mother, father)):
                cuts.append(Cut(path, start, count, head, child))
        elif kind == "conception":
            mother, father = extra
            if mother in gone_keys and (father is None or father in gone_keys):
                cuts.append(Cut(path, start, count, head, mother))
        elif kind == "event" and extra:
            owners = [k for k in gone_keys if k[0] == extra]
            if owners and extra not in kept_names:
                cuts.append(Cut(path, start, count, head, owners[0]))
    cuts.sort(key=lambda c: (str(c.path), c.start))
    return Plan(folder, game, slot, village, gone, kept, cuts, notes)


# ---------------------------------------------------------------------------
# Applying (the game closed, the player's confirmation given)
# ---------------------------------------------------------------------------

@dataclass
class Result:
    removed: list[Verdict]
    files: list[tuple[Path, Path, int]]          # (log, its copy, blocks removed)


def _copy_path(folder: Path, path: Path) -> Path:
    for k in range(1, 1000):
        candidate = tools.copy_before_repair(folder, path, BACKUP_SUFFIX + ("" if k == 1 else f"-{k}"))
        if not candidate.exists():
            candidate.parent.mkdir(parents=True, exist_ok=True)
            return candidate
    raise HistoryRevisionError(f"{path.name} has too many copies already; nothing was changed.")


def _write(path: Path, data: bytes) -> None:
    """Through a temporary file moved into place, then read back."""
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_bytes(data)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            try:
                temporary.unlink()
            except OSError:
                pass
    if path.read_bytes() != data:
        raise OSError(f"{path.name} did not read back as written")


def _restore(done: list[tuple[Path, Path]]) -> list[str]:
    """Every file already rewritten put back from its copy; the ones that could not be, by name."""
    failed = []
    for path, copy in reversed(done):
        try:
            _write(path, copy.read_bytes())
        except OSError:
            failed.append(str(path))
    return failed


def revise(folder: Path, game: int, slot: int, confirmed: Plan, processes=None,
           now: datetime | None = None, *, confirm: bool = False) -> Result:
    """Remove the villagers of `confirmed` (the plan the player saw and confirmed) that are STILL proven
    gone now: the logs are planned again, and only a villager gone in both is removed.  `confirm` must be
    True: the player's own confirmation (the checklist row is unticked by default)."""
    import vv_log_additions as additions
    import vv_save_backup
    folder = Path(folder)
    if not confirm:
        raise HistoryRevisionError("The history revision needs your confirmation; nothing was changed.")
    controller = processes if processes is not None else vv_save_backup.WindowsProcesses()
    tools._refuse_if_running(folder, controller)
    fresh = plan(folder, game, slot)
    wanted = confirmed.gone_keys & fresh.gone_keys
    removed = [v for v in fresh.gone if v.person.key in wanted]
    if not removed:
        return Result([], [])
    by_file: dict[Path, list[Cut]] = {}
    for cut in fresh.cuts:
        if cut.who is None or cut.who in wanted:
            by_file.setdefault(cut.path, []).append(cut)
    # A snapshot heading goes only when every villager under it goes (planned so); with a narrower
    # confirmation, a heading whose villagers are not all removed now stays.
    for path, cuts in list(by_file.items()):
        keep = []
        for cut in cuts:
            if cut.who is None:
                under = [c for c in fresh.cuts if c.path == path and c.who is not None and c.when == cut.when]
                if any(c.who not in wanted for c in under):
                    continue
            keep.append(cut)
        by_file[path] = keep
    checker = tools.load_checker()
    boundaries = [dat for dat in tools.layout.places(folder, checker.LOG_WORDS.format(game=game)) if dat.is_file()]
    docs = []
    for path, cuts in by_file.items():
        doc = additions._Doc(path)
        for cut in cuts:
            doc.removed.update(range(cut.start, cut.start + cut.count))
            doc.removes.append((cut.start, cut.count, KIND_ID))
        if doc.changed:
            docs.append((doc, sum(1 for c in cuts if c.who is not None)))
    done: list[tuple[Path, Path]] = []
    written: list[tuple[Path, Path, int]] = []
    copies: dict[Path, Path] = {}
    try:
        for dat in boundaries:
            copy = _copy_path(folder, dat)
            shutil.copyfile(dat, copy)
            copies[dat] = copy
        for doc, count in docs:
            copy = _copy_path(folder, doc.path)
            with open(doc.path, "rb") as source, open(copy, "xb") as out:
                out.write(source.read())
            if copy.read_bytes() != doc.raw:
                raise OSError(f"the copy of {doc.path.name} did not read back")
            # Recorded before the write: a file that fails its read-back has already been replaced.
            done.append((doc.path, copy))
            _write(doc.path, doc.render().encode("latin-1"))
            written.append((doc.path, copy, count))
        for doc, _count in docs:
            additions._move_boundaries(folder, doc)
    except OSError as exc:
        failed = _restore(done + [(dat, copy) for dat, copy in copies.items()]) if done or copies else []
        where = f" These could not be put back: {', '.join(failed)}." if failed else ""
        raise HistoryRevisionError(
            f"The history revision failed ({exc}); every log it had changed was put back from its copy in "
            f"Copies Made Before Repairs.{where}") from exc
    # The Repairs log: one line per villager removed.
    fixes = []
    for v in removed:
        p = v.person
        logs = sorted({_rel(folder, c.path) for cuts in by_file.values() for c in cuts if c.who == p.key})
        dates = sorted({c.when for cuts in by_file.values() for c in cuts if c.who == p.key and c.when})
        sex = p.sex or "sex unknown"
        text = (f"{p.name} ({sex}, head {p.head}, body {p.body}) -- from {', '.join(logs)}"
                + (f"; Village History snapshots of {', '.join(dates)}" if dates else ""))
        fixes.append(tools.WordFix(text, -1, ", ".join(c.name for _p, c, _n in written)))
    try:
        village = checker.births_log(folder, game, slot)[0].village
    except Exception:
        village = confirmed.village
    tools.note_word_repair(folder, game, village, fixes, now, checked=CHECKED, corrected=CORRECTED, slot=slot)
    return Result(removed, written)


def hidden_in_tree(folder: Path, game: int, slot: int) -> set[tuple]:
    """The (name, head, body) of every villager proven gone (a tribe started over under the same name): the
    Family Tree Maker's "Hide villagers not in the current save".  Empty when nothing can be read."""
    try:
        return plan(folder, game, slot).gone_keys
    except (tools.LogToolError, OSError, ValueError):
        return set()


def without(village, keys: set[tuple]):
    """The family tree's village (src/vv_genealogy.py Village) without the villagers of `keys` who are not
    alive -- the tree only; nothing is changed in any file.  A parent so hidden is no longer drawn as one."""
    import dataclasses
    if not keys:
        return village
    hidden = {pid for pid, p in village.people.items() if not p.alive and p.key in keys}
    if not hidden:
        return village
    people = {}
    for pid, p in village.people.items():
        if pid in hidden:
            continue
        people[pid] = dataclasses.replace(p, father=None if p.father in hidden else p.father,
                                          mother=None if p.mother in hidden else p.mother)
    return dataclasses.replace(village, people=people,
                               base_generation={k: v for k, v in village.base_generation.items() if k not in hidden})
