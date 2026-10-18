"""The always-on, read-only reconciliation of a village's records, logs and files (all five games).

The owner (2026-10-11), after "Iruwa Okelani" (Birth 252, head 12, body 18) became a second living
"Tiki Alosaka" in her A New Home village with no record of it, and a checker that had been taught to
call that "renamed since birth: OK":

    "FOR ALL 5 GAMES: THE PATCHER SHOULD ALWAYS DO A READ-ONLY RECONCILIATION OF RECORDS, LOGS, AND
    FILES TO MAKE SURE ABSOLUTELY NOTHING IS LOST. IF THERE ARE CONTRADICTIONS ASK THE PLAYER."
    "THE PATCHER MUST BE ABLE TO TELL APART VILLAGERS."
    "THE VILLAGE RECORDS WILL CHANGE IF PEOPLE DIE OR ARE BORN, ESPECIALLY AT MAX POPULATION --
    ACCOUNT FOR THAT, I REACHED 256 VILLAGERS."

WHAT IS READ (never written).  For one slot's village, in every game:

  * the save and the game's own older generations of it (A New Home to New Believers keep the
    slot's save as "<name><slot>.ldw" and two older ones, "<name><slot+20>.ldw" and
    "<name><slot+40>.ldw" -- docs/start-over-reset-hook.md); one that holds another village is
    left out.  The patcher's Backups folder is never read;
  * every Village History snapshot and the Village Population page of this village (the shared
    folders older builds wrote and the slot's own, under every name the village has had);
  * the Births and Conceptions log (Birth, Arrived, Appearance changed and Name changed records),
    the Deaths and Disappearances log (Death, Disappeared, Left the tribe), the Unaccounted log,
    the Island Events log (new villagers, head and body changes, name changes), the Repairs log;
  * the copies the patcher keeps of its logs and data files (".before-..." beside them, and in
    Copies Made Before Repairs) and the data files themselves, for FILE-level loss;
  * A New Home's Parentage Records roster, for the record slots reused since it was written.

WHO IS WHO.  Villagers are followed by identity, never by a record number: record slots are reused
at the cap (a death frees one, the next birth takes it) and every load packs the records, so a
record number holds different villagers over time (the owner's village at 256).  Two rosters in a
row (two History snapshots, two generations of the save, the last snapshot and the save) are
matched on name, head, body and sex, namesakes in age order; whoever is left on either side is
followed by what does not change -- sex, head and body, likes and dislikes, the parents the record
keeps -- with the age only moving on, through the records that explain a change (Death,
Disappeared, Left the tribe, Unaccounted, Appearance changed, an island event's change).

WHAT IS REPORTED.  Every contradiction becomes a numbered QUESTION naming the exact villagers,
records and files, with its choices (keep as is / which record is right / don't know); nothing is
changed until the player answers in Repair Saves & Logs, and an answer is remembered
(src/vv_log_decisions.py).  What the game itself explains is a NOTE: names, looks, likes and
dislikes repeat from fixed pools, twins share everything but the name, a record slot holding a
different villager after deaths is normal, the Villager Details screen hides 18+ parents, a
Golden Child (A New Home only) is a birth.  Questions:

  * a villager whose name changed (a Birth or Arrived record, a snapshot or an older save says one
    name, the save another) -- recorded by a "Name changed" record or not, the player is asked
    which is right (the Villager Details screen can copy one villager's name onto another, stock
    0x44A79B / 0x44A849 / 0x44A738);
  * head or body changed with no Appearance changed or island event record; sex, likes or
    dislikes or parents changed; the age going backwards;
  * a villager present in one roster and gone from the next with no Death, Disappeared, Left the
    tribe or Unaccounted record: possibly lost;
  * a file missing, cut short, smaller than the copy kept before a repair beyond what the Repairs
    log says was taken out, or the save older than the logs (replaced by an older copy).

Check Saves & Logs shows it all (verdict ASK for a question); Repair Saves & Logs asks the
questions; the patcher's tribe pickers run it whenever a village is chosen; the report is written
to "Virtual Villagers Fun Patcher\\Save <n>\\Logs\\Reconciliation\\Virtual Villagers <g> Reconciliation -
Save <n>.txt" (the save's own folder) -- the
only file this module writes, and only through `export`.
"""
from __future__ import annotations

import os
import re
import struct
import zlib
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import vv_save_layout as layout

REPORT_FOLDER = "Reconciliation"
REPORT_NAME = "Virtual Villagers {game} Reconciliation - Save {slot}.txt"
DECISION_KIND = "reconcile"
KEEP = "Keep as is"
DONT_KNOW = "Don't know (leave it)"
GAME_TITLES = {1: "A New Home", 2: "The Lost Children", 3: "The Secret City", 4: "The Tree of Life",
               5: "New Believers"}

DEPARTURE = re.compile(r"^(Death \d+|Disappeared(?: \d+)?|Left the tribe|Unaccounted \d+)\s*$")
BIRTH = re.compile(r"^Birth(?: \d+)?\s*$")
ARRIVED = re.compile(r"^Arrived \d+\s*$")
EVENT = re.compile(r"^Island event \d+\s*$")
CHANGE = re.compile(r"^\s*(.*?) -> (.*?)\s*$")
# A record's own heading counted in a log or its copy, for file-level loss.
RECORD_HEAD = re.compile(r"^(Birth(?: \d+)?|Conception \d+|Arrived \d+|Death \d+|Disappeared(?: \d+)?|"
                         r"Unaccounted \d+|Island event \d+|Repair \d+|Lost before birth|Left the tribe|"
                         r"Appearance changed|Name changed|Epitaph changed|=== .* ===)\s*$")


def _checker():
    import vv_log_tools
    return vv_log_tools.load_checker()


class ReconcileError(Exception):
    """The village could not be reconciled at all; the message says why."""


# ---------------------------------------------------------------------------
# What one source says about one villager
# ---------------------------------------------------------------------------

@dataclass
class Seen:
    name: str
    head: int | None
    body: int | None
    sex: str | None = None
    age: int | None = None
    likes: frozenset | None = None          # None: the source does not say
    dislikes: frozenset | None = None
    father: str | None = None               # None: the source does not say; "": none
    mother: str | None = None
    rank: int | None = None                 # the record slot (a save only)
    title: str | None = None                # a snapshot's "Custom title"
    title_id: int | None = None             # the save's custom-title identity (native/shared/custom_titles.h)
    title_looks: dict | None = None         # the save's age, head, body, sex and skills (src/vv_titles_file.py)
    at: int | None = None                   # the name's offset in the save (a save only)
    record: int | None = None               # the record the game loads them into (vv_lost_titles._record_index)

    @property
    def key(self) -> tuple:
        return (self.name, self.head, self.body)

    def looks(self) -> str:
        return f"head {self.head}, body {self.body}"

    def described(self) -> str:
        age = f", age {self.age}" if self.age is not None else ""
        return f"{self.name} ({self.sex + ', ' if self.sex else ''}{self.looks()}{age})"


@dataclass
class Census:
    """Everyone one source lists at one moment: a History snapshot, the Population page, a save."""
    label: str
    when: str                               # "YYYY-MM-DD HH:MM:SS", sortable
    kind: str                               # "history" | "population" | "save"
    people: list[Seen]
    path: Path | None = None


@dataclass
class Record:
    """One record of one villager in the logs (a Birth, an Arrived record, a departure...)."""
    heading: str
    who: Seen
    path: Path
    extra: dict = field(default_factory=dict)


@dataclass(frozen=True)
class TitleAction:
    """What one answer to a pending-title question does to the Custom Titles file (settle_titles): bind
    the pending entry (identity, title) to the villager named -- whose name is at `at` in the save, in
    record `record`, with the looks the reconciliation read -- or clear it.

    WHICH pending entry (v1.35.71 v2): two villagers of one identity may each have been given the same
    title text, and both entries can wait at once.  Each question is about ONE entry: `entry` is its
    place in the file when the question was asked, `raw` its bytes then and `twins` how many pending
    entries had that identity and title then.  settle_titles changes that entry only if the file still
    holds it there, byte for byte, with the same number of twins -- else nothing, and it is asked again."""
    kind: str                               # "bind" | "clear"
    identity: int
    title: str
    name: str | None = None
    at: int | None = None
    record: int | None = None
    looks: dict | None = field(default=None, compare=False, hash=False)
    entry: int | None = None                # the entry's place in the file when asked
    raw: bytes | None = None                # the entry's bytes when asked (vv_titles_file.entry_bytes)
    twins: int = 1                          # pending entries of that identity and title when asked


@dataclass
class Finding:
    kind: str                               # "ask" | "note"
    topic: str
    qid: str
    text: str
    options: list[str] = field(default_factory=list)
    rename: tuple | None = None             # ((name, head, body) now, the name the record gives)
    answer: str | None = None               # the player's remembered answer
    title_actions: dict | None = None       # a pending title's answers that change the file: option -> TitleAction


@dataclass
class Reconciliation:
    folder: Path
    game: int
    slot: int
    village: str | None
    findings: list[Finding]
    sources: list[str]
    followed: int

    @property
    def questions(self) -> list[Finding]:
        return [f for f in self.findings if f.kind == "ask"]

    @property
    def notes(self) -> list[Finding]:
        return [f for f in self.findings if f.kind == "note"]

    def lines(self) -> list[tuple[str, str]]:
        """(verdict, text) for Check Saves & Logs: ASK for each question, numbered, then the NOTEs."""
        out = []
        for n, f in enumerate(self.questions, 1):
            choices = " / ".join(f.options)
            out.append(("ASK", f"Question {n}: {f.text} [{choices}]"))
        for f in self.notes:
            out.append(("NOTE", f.text))
        if not self.questions:
            out.append(("OK", f"{self.followed} villager(s) followed through {len(self.sources)} source(s): "
                              "no contradiction and nothing lost"))
        return out

    def summary(self) -> str:
        q = len(self.questions)
        if not q:
            return f"Reconciliation (read-only): nothing lost, no contradiction ({self.followed} villagers followed)."
        return (f"Reconciliation (read-only): {q} question(s) only you can answer -- see Check Saves & Logs, "
                "and answer them in Repair Saves & Logs. Nothing was changed.")

    def render(self) -> str:
        head = [f"Virtual Villagers {self.game} ({GAME_TITLES.get(self.game, '?')}) -- read-only reconciliation",
                f"Save {self.slot}: {self.village or '(the tribe name could not be read)'}",
                f"Written {datetime.now():%Y-%m-%d %H:%M:%S}. Nothing was changed: every question waits for your "
                "answer in Repair Saves & Logs.", "",
                f"Villagers followed: {self.followed}", "Sources read:"]
        head += [f"  {s}" for s in self.sources]
        body = ["", f"Questions ({len(self.questions)}):"]
        for n, f in enumerate(self.questions, 1):
            body.append(f"  {n}. {f.text}")
            body.append(f"     Choices: {' / '.join(f.options)}")
        if not self.questions:
            body.append("  (none)")
        body += ["", f"Notes ({len(self.notes)}):"]
        body += [f"  - {f.text}" for f in self.notes] or ["  (none)"]
        return "\n".join(head + body) + "\n"


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

def _words(value: str | None) -> frozenset | None:
    if value is None:
        return None
    value = value.strip()
    if value in ("", "(none)", "none"):
        return frozenset()
    return frozenset(w.strip().lower() for w in value.split(",") if w.strip())


def _int(value: str | None) -> int | None:
    try:
        return int(str(value).strip().split()[0])
    except (ValueError, IndexError, AttributeError):
        return None


def _when(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    except OSError:
        return ""


def save_generations(folder: Path, game: int, slot: int) -> list[Path]:
    """The game's own two older generations of the slot's save, oldest first (by time), then the slot's
    save itself, LAST WHATEVER ITS TIME.  Everything after this treats the last entry as the current
    save; sorted in by time, a current save restored from an older copy with its time kept (as the
    patcher's own backups keep it) sorted before a generation, and was then compared as an old copy --
    the very "replaced by an older copy" case the checks exist to find went unseen."""
    stem = _checker().SAVE_STEMS[game]
    older = [p for p in (Path(folder) / f"{stem}{n}.ldw" for n in (slot + 40, slot + 20)) if p.is_file()]
    current = Path(folder) / f"{stem}{slot}.ldw"
    return sorted(older, key=lambda p: p.stat().st_mtime) + ([current] if current.is_file() else [])


def read_save(path: Path, game: int) -> tuple[list[Seen], list[Seen]]:
    """(the living, the bodies awaiting burial) of one save file, each with what the save keeps."""
    import vv_last_names as ln
    import vv_lost_titles as lt
    import vv_titles_file as titles_file
    checker = _checker()
    data = path.read_bytes()
    f = ln.FIELDS[game]
    age_at = -0x28 if game == 1 else checker.LAYOUTS[game].age
    try:
        everyone = ln._entries(game, data, bodies=True)
        living = set(ln._entries(game, data))
    except (ln.LastNamesError, ValueError, IndexError, struct.error) as exc:
        raise ReconcileError(f"{path.name}: the villagers could not be read ({exc})") from exc
    alive, bodies = [], []
    if game == 1:
        first = checker.VV1_BLOCK0 - checker.VV1_BASE + 0x370
        records = {at: (at - first) // checker.VV1_STRIDE for at in everyone}
    else:
        try:
            records = {at: k for k, at in enumerate(checker.villager_offsets(game, data, []))}
        except ValueError:
            records = {}
    for rank, at in enumerate(everyone):
        def i32(off: int) -> int:
            return struct.unpack_from("<i", data, at + off)[0]
        prefs = {}
        for label, off in (("likes", f.likes), ("dislikes", f.dislikes)):
            values = list(struct.unpack_from(f"<{f.slots}i", data, at + off))
            prefs[label] = _words(lt.list_text(game, values))
        father = mother = None
        if f.father is not None:
            father = data[at + f.father:at + f.father + f.parent_cap].split(b"\0", 1)[0].decode("latin-1")
            mother = data[at + f.mother:at + f.mother + f.parent_cap].split(b"\0", 1)[0].decode("latin-1")
        seen = Seen(data[at:at + f.name_cap].split(b"\0", 1)[0].decode("latin-1"), i32(f.head), i32(f.body),
                    "Male" if i32(f.sex) == f.male else "Female", i32(age_at), prefs["likes"], prefs["dislikes"],
                    father, mother, rank, None, ln._title_identity(data, at, f),
                    titles_file.looks_from_save(game, data, at), at, records.get(at))
        (alive if at in living else bodies).append(seen)
    return alive, bodies


def _sub_person(lines: list[str], label: str) -> Seen | None:
    """A Birth record's "  Child:" / "  Mother:" / "  Father:" with the lines indented under it."""
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
            return Seen(name, _int(values.get("Head")), _int(values.get("Body")), values.get("Sex"), None,
                        _words(values.get("Likes")), _words(values.get("Dislikes")))
    return None


def _snapshot_person(b) -> Seen:
    import vv_genealogy as gen
    parents = gen._snapshot_parents(b.lines)
    has_parents = any(line.startswith("  Parents:") for line in b.lines)
    return Seen(b.value("Name") or "", b.int_value("Head"), b.int_value("Body"), b.value("Sex"),
                b.int_value("Age"), _words(b.value("Likes")), _words(b.value("Dislikes")),
                parents["Father"][0] if "Father" in parents else ("" if has_parents else None),
                parents["Mother"][0] if "Mother" in parents else ("" if has_parents else None),
                title=b.value("Custom title"))


@dataclass
class Logs:
    censuses: list[Census] = field(default_factory=list)
    births: list[Record] = field(default_factory=list)
    arrivals: list[Record] = field(default_factory=list)
    departures: list[Record] = field(default_factory=list)
    looks_changed: list[tuple[str, int | None, int | None, int | None, int | None]] = field(default_factory=list)
    names_changed: list[Record] = field(default_factory=list)
    new_by_event: list[Record] = field(default_factory=list)
    event_changes: list[tuple[str, str, str, str]] = field(default_factory=list)   # (name, field, old, new)
    files: list[Path] = field(default_factory=list)


def read_logs(folder: Path, game: int, slot: int, villages: set[str] | None) -> Logs:
    import vv_log_additions as additions
    checker = _checker()
    out = Logs()
    snapshots: dict[str, Census] = {}
    population: Census | None = None
    for path in checker.log_files(Path(folder)):
        try:
            found = additions.blocks(path)
        except OSError:
            continue
        mine = [b for b in found if b.of(slot, game, villages)]
        if not mine:
            continue
        out.files.append(path)
        for b in mine:
            head = b.heading
            if head.startswith("Villager ") and additions.is_population(path):
                if population is None or population.path != path:
                    population = Census(f"the Village Population page ({path.name})", _when(path), "population",
                                        [], path)
                population.people.append(_snapshot_person(b))
            elif head.startswith("Villager ") and b.date:
                census = snapshots.get(b.date)
                if census is None:
                    census = snapshots[b.date] = Census(f"the Village History snapshot of {b.date}", b.date,
                                                        "history", [], path)
                census.people.append(_snapshot_person(b))
            elif BIRTH.match(head):
                child = _sub_person(b.lines, "Child")
                if child is not None:
                    father, mother = _sub_person(b.lines, "Father"), _sub_person(b.lines, "Mother")
                    child.father = father.name if father else ""
                    child.mother = mother.name if mother else ""
                    out.births.append(Record(head, child, path))
            elif ARRIVED.match(head):
                out.arrivals.append(Record(head, Seen(b.value("Name") or "", b.int_value("Head"),
                                                      b.int_value("Body"), b.value("Sex"), None,
                                                      _words(b.value("Likes")), _words(b.value("Dislikes"))),
                                           path, {"how": b.value("How") or ""}))
            elif DEPARTURE.match(head):
                out.departures.append(Record(head, Seen(b.value("Name") or "", b.int_value("Head"),
                                                        b.int_value("Body"), b.value("Sex"),
                                                        _int(b.value("Age at death"))), path))
            elif head == "Appearance changed":
                out.looks_changed.append((b.value("Name") or "", _int(b.value("Old head")), _int(b.value("Old body")),
                                          _int(b.value("New head")), _int(b.value("New body"))))
            elif head == "Name changed":
                out.names_changed.append(Record(head, Seen(b.value("Name") or "", b.int_value("Head"),
                                                           b.int_value("Body"), None, _int(b.value("Age"))),
                                                path, {"old": b.value("Old name") or ""}))
            elif EVENT.match(head):
                name = b.value("Name") or ""
                changed = CHANGE.match(name)
                if changed:
                    out.event_changes.append((changed.group(2), "Name", changed.group(1), changed.group(2)))
                    name = changed.group(2)
                if (b.value("New villager") or "").lower().startswith("yes"):
                    out.new_by_event.append(Record(head, Seen(name, b.int_value("Head"), b.int_value("Body"),
                                                              b.value("Sex")), path))
                for line in b.lines[1:]:
                    m = re.match(r"^  ([^:]+): (.*?) -> (.*?)\s*$", line)
                    if m and name:
                        out.event_changes.append((name, m.group(1), m.group(2), m.group(3)))
    out.censuses = sorted(snapshots.values(), key=lambda c: c.when)
    if population is not None:
        out.censuses.append(population)
        out.censuses.sort(key=lambda c: c.when)
    return out


# ---------------------------------------------------------------------------
# Following villagers from one roster to the next
# ---------------------------------------------------------------------------

def _compatible(a: frozenset | None, b: frozenset | None) -> bool:
    """Likes or dislikes that MAY be one villager's, for telling villagers apart (never for asking about
    a change): unknown on a side, or one list within the other (records written before v1.35.68 printed
    only the first filled slot)."""
    return a is None or b is None or a <= b or b <= a


# The History and Population writers listed only each villager's FIRST like and dislike until v1.35.68;
# the owner's A New Home village's first full-list snapshot is 2026-10-11 20:19:48, its last one-word
# snapshot 2026-10-10 12:50:39.  A roster from before this, with no villager listing two words, is read
# as one-word: its single word may stand for a longer list (src/vv_log_tools.py preference_words).
FULL_LISTS_FROM = "2026-10-11 20:19:00"


def one_word_writer(census: "Census") -> bool:
    """Whether this roster was written by a writer that listed only the first like and dislike: a History
    snapshot or Population page dated before FULL_LISTS_FROM in which nobody lists two words.  A save
    always keeps every slot."""
    if census.kind == "save" or census.when >= FULL_LISTS_FROM:
        return False
    return not any(len(s.likes or ()) > 1 or len(s.dislikes or ()) > 1 for s in census.people)


def _prefs_agree(x: frozenset | None, y: frozenset | None, x_one_word: bool, y_one_word: bool) -> bool:
    """Two looks at one villager's likes (or dislikes): the same set -- a word lost or gained is a change
    -- unless a side does not say, or a one-word roster's single word is the first of the other's."""
    if x is None or y is None or x == y:
        return True
    # "(none)" was printed only when every slot was empty, so an empty one-word list is still exact.
    if x_one_word and len(x) == 1 and x <= y:
        return True
    if y_one_word and len(y) == 1 and y <= x:
        return True
    return False


def _same_parent(a: str | None, b: str | None) -> bool:
    return a is None or b is None or a == "" or b == "" or a == b


def _could_be(a: Seen, b: Seen, game: int) -> bool:
    """Whether b may be the same villager as a, a later look at them (age only moves on)."""
    return ((a.sex is None or b.sex is None or a.sex == b.sex)
            and _compatible(a.likes, b.likes) and _compatible(a.dislikes, b.dislikes)
            and _same_parent(a.father, b.father) and _same_parent(a.mother, b.mother)
            and (a.age is None or b.age is None or b.age >= a.age))


def _pair(a: list[Seen], b: list[Seen]) -> tuple[list[tuple[Seen, Seen]], list[Seen], list[Seen]]:
    """Exact matches on name, head and body (sex too where both say it), namesakes in age order."""
    groups_a: dict[tuple, list[Seen]] = {}
    groups_b: dict[tuple, list[Seen]] = {}
    for s in a:
        groups_a.setdefault(s.key, []).append(s)
    for s in b:
        groups_b.setdefault(s.key, []).append(s)
    pairs, gone, new = [], [], []
    for key, olds in groups_a.items():
        news = list(groups_b.get(key, []))
        olds = sorted(olds, key=lambda s: -(s.age or 0))
        news = sorted(news, key=lambda s: -(s.age or 0))
        for old in olds:
            match = next((n for n in news if (old.sex is None or n.sex is None or old.sex == n.sex)
                          and (old.age is None or n.age is None or n.age >= old.age)), None)
            if match is None:
                match = next((n for n in news if old.sex is None or n.sex is None or old.sex == n.sex), None)
            if match is None:
                gone.append(old)
            else:
                news.remove(match)
                pairs.append((old, match))
        groups_b[key] = news
    for news in groups_b.values():
        new.extend(news)
    return pairs, gone, new


def names_related(game: int, old: str, new: str) -> bool:
    """A last name or a numeral given or dropped, or a name the Villager Details screen cut: what the
    patcher's own Last Names, Number Duplicate Names and cut-name repairs do (the checker's rule)."""
    checker = _checker()
    return checker.names_related(game, old, new) or checker.names_related(game, new, old)


class _Builder:
    def __init__(self, folder: Path, game: int, slot: int, logs: Logs, answered: dict[str, str]):
        self.folder, self.game, self.slot, self.logs = folder, game, slot, logs
        self.answered = answered
        self.findings: dict[str, Finding] = {}
        self.departed = {r.who.key for r in logs.departures}
        self.departed_names = {r.who.name for r in logs.departures if r.who.head is None}
        self.recorded = {r.who.key for r in logs.births + logs.arrivals + logs.new_by_event}
        self.slot_reused = 0                # record slots holding another villager than before
        self.slot_moved = 0                 # villagers in another slot than before

    # -- findings --------------------------------------------------------------------------------
    def ask(self, topic: str, qid: str, text: str, options: list[str], rename: tuple | None = None,
            title_actions: dict | None = None) -> None:
        if qid in self.findings:
            if text not in self.findings[qid].text:
                self.findings[qid].text += " Also: " + text
            return
        answer = self.answered.get(qid)
        if answer is not None and answer != DONT_KNOW and answer not in (title_actions or {}):
            self.findings[qid] = Finding("note", topic, qid, f"{text} You answered: \"{answer}\".", options,
                                         rename, answer)
        else:
            # An answer that was to change the Custom Titles file and the title still waits (the file was
            # put back, or changed again since): asked again, never taken as settled.
            self.findings[qid] = Finding("ask", topic, qid, text, options + [DONT_KNOW], rename,
                                         title_actions=title_actions)

    def note(self, topic: str, qid: str, text: str) -> None:
        if qid not in self.findings:
            self.findings[qid] = Finding("note", topic, qid, text)

    # -- explanations ----------------------------------------------------------------------------
    def identities(self, s: Seen) -> set[tuple]:
        """Every (name, head, body) this villager had from `s` on, through what the logs record: an
        Appearance changed record, a Name changed record, an island event's Name, Head or Body step."""
        steps_looks = [((n, oh, ob), (n, nh, nb)) for n, oh, ob, nh, nb in self.logs.looks_changed]
        renames = [(r.extra.get("old", ""), r.who.name, r.who.head, r.who.body) for r in self.logs.names_changed]
        events = [(who, what, o, n) for who, what, o, n in self.logs.event_changes]
        reached, todo = {s.key}, [s.key]
        while todo:
            name, head, body = todo.pop()
            following = [after for before, after in steps_looks if before == (name, head, body)]
            following += [(new, head, body) for old, new, h, b in renames
                          if old == name and (h is None or (h, b) == (head, body))]
            for who, what, o, n in events:
                if what == "Name" and o == name:
                    following.append((n, head, body))
                elif what == "Head" and who == name and _int(o) == head and _int(n) is not None:
                    following.append((name, _int(n), body))
                elif what == "Body" and who == name and _int(o) == body and _int(n) is not None:
                    following.append((name, head, _int(n)))
            for state in following:
                if state not in reached:
                    reached.add(state)
                    todo.append(state)
        return reached

    def left(self, s: Seen) -> str | None:
        """The record that says this villager died or went, if any -- under the name and looks they had
        then, followed through the recorded changes since `s` (review of #585: a villager whose looks
        or name changed, recorded, before a recorded death was asked about as possibly lost).

        The record must be able to be THEM (review of #585): names and looks come from fixed pools, so a
        Death record of a villager of the other sex with the same name, head and body says nothing of
        this one.  (The age is not used: after a restored backup a villager can die younger than a later
        snapshot saw them.)"""
        known = self.identities(s)
        names = {name for name, _h, _b in known}
        for r in self.logs.departures:
            if not (r.who.key in known or (r.who.head is None and r.who.name in names)):
                continue
            if s.sex and r.who.sex and s.sex.strip().lower() != r.who.sex.strip().lower():
                continue
            return r.heading
        return None

    def looks_recorded(self, old: Seen, new: Seen) -> bool:
        """Whether recorded changes lead from old's looks to new's, each step EXACTLY as recorded: an
        Appearance changed record (old head and body -> new head and body), or an island event's
        "Head: a -> b" / "Body: a -> b" for this villager, which changes that one value from a to b and
        leaves the other.  Any other change -- another value, or the part no record names -- is asked
        (review of #585: one recorded head change used to excuse every later difference)."""
        names = {old.name, new.name}
        steps = [((oh, ob), (nh, nb)) for name, oh, ob, nh, nb in self.logs.looks_changed if name in names]
        events = [(what, _int(o), _int(n)) for name, what, o, n in self.logs.event_changes
                  if name in names and what in ("Head", "Body")]
        start, goal = (old.head, old.body), (new.head, new.body)
        reached, todo = {start}, [start]
        while todo:
            head, body = todo.pop()
            following = [after for before, after in steps if before == (head, body)]
            following += [(n, body) for what, o, n in events if what == "Head" and o == head and n is not None]
            following += [(head, n) for what, o, n in events if what == "Body" and o == body and n is not None]
            for state in following:
                if state not in reached:
                    reached.add(state)
                    todo.append(state)
        return goal in reached

    def prefs_recorded(self, name: str, what: str, old: frozenset, new: frozenset) -> bool:
        """Whether island events recorded for this villager lead from one likes (or dislikes) list to the
        other, each step exactly as recorded ("Likes: a, b -> a, c")."""
        events = [(_words(o), _words(n)) for who, field_, o, n in self.logs.event_changes
                  if who == name and field_.lower() == what]
        reached, todo = {old}, [old]
        while todo:
            current = todo.pop()
            for before, after in events:
                if before == current and after is not None and after not in reached:
                    reached.add(after)
                    todo.append(after)
        return new in reached

    def name_record(self, old: Seen, new: Seen) -> Record | None:
        for r in self.logs.names_changed:
            if r.extra.get("old") == old.name and r.who.name == new.name:
                return r
        return None

    # -- one roster to the next ------------------------------------------------------------------
    def compare(self, a: Census, b: Census, bodies: list[Seen] | None = None, restored: bool = False) -> None:
        """b after a.  `restored`: b is the save and OLDER than the snapshot a (a save restored from an
        older copy, its time kept): the save going back in time is files()'s one question, so ages and
        villagers new to the save are not looked at; everything else -- a villager gone, likes,
        parents, looks -- is."""
        pairs, gone, new = _pair(a.people, b.people)
        game = self.game
        # A save older than the roster it is compared with: whoever is missing from it is most likely in no
        # save only because of a quit without saving (Alt-F4) or a restored backup -- said so.
        restore_why = (f" -- or, as {b.label} is older than {a.label}, most likely only missing from the save "
                       "after a quit without saving (Alt-F4) or a restored backup") if restored else ""
        a_one_word, b_one_word = one_word_writer(a), one_word_writer(b)
        if a.kind == "save" and b.kind == "save":
            # Record slots: one that holds another villager now than in the older copy -- a death freed
            # it and a later villager took it, or a load packed the records (the owner's village at 256).
            held = {s.rank: s.key for s in a.people if s.rank is not None}
            self.slot_reused += sum(1 for s in b.people if s.rank in held and held[s.rank] != s.key)
        backs = [] if restored else [(old, now) for old, now in pairs
                                     if old.age is not None and now.age is not None and now.age < old.age]
        if len(backs) >= 3 and len(backs) * 2 >= len(pairs):
            # The whole village went back in time: one question, not one per villager.
            o, n = backs[0]
            self.ask("age", f"restore|{a.when}|{b.when}",
                     f"{len(backs)} of the {len(pairs)} villagers in both are younger in {b.label} than in "
                     f"{a.label} (for example {n.name}, {n.looks()}: {o.age} -> {n.age} game units): the village "
                     "went back in time -- most likely a backup restored, or a quit without saving (Alt-F4: the "
                     "game saves only on a clean quit), not a fault?",
                     [f"{KEEP} (I restored or replaced the save)"])
            backs = []
        for old, now in backs:
            self.ask("age", f"age|{now.key}|{a.when}|{b.when}",
                     f"{now.name} ({now.looks()}) is {old.age} game units old in {a.label} but {now.age} in "
                     f"{b.label}: the age went backwards, and no record says why. Is this the same villager?",
                     [f"{KEEP} (the same villager; the age was changed)", "Another villager (the first is lost)"])
        for old, now in pairs:
            if old.sex and now.sex and old.sex != now.sex:
                self.ask("sex", f"sex|{now.key}", f"{now.name} ({now.looks()}) is {old.sex} in {a.label} but "
                         f"{now.sex} in {b.label}. Which is right?", [f"{KEEP} ({now.sex})", f"{old.sex}"])
            # Likes and dislikes: any word lost or gained between two looks at one villager is a change
            # (review of #585: a save that lost one like used to pass as "one list within the other").
            # Only a roster written when the writer listed the first word alone may show one word of a
            # longer list -- a note about that roster, never about the villager.
            for what in ("likes", "dislikes"):
                x, y = getattr(old, what), getattr(now, what)
                if x is None or y is None or x == y:
                    continue
                if _prefs_agree(x, y, a_one_word, b_one_word):
                    short = a if a_one_word and len(x) == 1 else b
                    self.note("one-word", f"one-word|{short.when}",
                              f"{short.label[:1].upper()}{short.label[1:]} was written before "
                              f"{FULL_LISTS_FROM[:16]}, when the patcher's "
                              "History and Population pages listed only each villager's first like and first "
                              "dislike: a single word there may stand for a longer list. Not a change.")
                    continue
                if self.prefs_recorded(now.name, what, x, y) or self.prefs_recorded(old.name, what, x, y):
                    continue
                self.ask(what, f"{what}|{now.key}|{a.when}",
                         f"{now.name} ({now.looks()}) {what}: {', '.join(sorted(x)) or '(none)'} in {a.label}, "
                         f"{', '.join(sorted(y)) or '(none)'} in {b.label}, and no island event records the "
                         "change.", [f"{KEEP} (the change is right)"])
            # Parents: a known parent becoming another, or becoming blank, between two looks at one
            # villager (review of #585).  None means the source does not say (A New Home's save keeps no
            # parents); "" is a source saying "none".  A blank becoming known is a parent recorded later
            # (Restore A New Home Parents), not a loss.
            for what in ("father", "mother"):
                x, y = getattr(old, what), getattr(now, what)
                if not x or y is None or x == y:
                    continue
                if y == "":
                    self.ask("parents", f"{what}|{now.key}|{x}|",
                             f"{now.name} ({now.looks()}): {what} {x} in {a.label}, none in {b.label}. Was the "
                             f"{what} lost?", [f"{KEEP} (none)", f"{x}"])
                else:
                    self.ask("parents", f"{what}|{now.key}|{x}|{y}",
                             f"{now.name} ({now.looks()}): {what} {x} in {a.label}, {y} in {b.label}. Which is "
                             "right?", [f"{KEEP} ({y})", f"{x}"])
            if a.kind == "save" and b.kind == "save" and old.rank is not None and now.rank is not None \
                    and old.rank != now.rank:
                self.slot_moved += 1
        # Who is gone from a, and who is new in b.
        unexplained_new = list(new)
        plain_lost: list[Seen] = []
        for old in gone:
            # A save OLDER than the roster (restored): whoever the roster lists was alive after the save was
            # written, so a Death or Disappeared record -- written later still -- never explains their being
            # missing from it (review of #585).
            why = None if restored else self.left(old)
            if why is not None:
                continue
            if bodies is not None and any(x.key == old.key for x in bodies):
                continue                                    # a body awaiting burial: its Death record comes then
            fits = [n for n in unexplained_new if _could_be(old, n, game)
                    and ((n.head, n.body) == (old.head, old.body) or n.name == old.name)]
            same_name = [n for n in fits if n.name == old.name]
            same_looks = [n for n in fits if (n.head, n.body) == (old.head, old.body) and n.name != old.name]
            if same_name and len(same_name) == 1:
                n = same_name[0]
                unexplained_new.remove(n)
                if self.looks_recorded(old, n):
                    continue
                self.ask("looks", f"looks|{old.key}|{n.key}",
                         f"{old.name}: {old.looks()} in {a.label}, {n.looks()} in {b.label}, and no Appearance "
                         "changed or island event record says the looks changed. Is this the same villager?",
                         [f"{KEEP} (the same villager; the looks changed)"])
            elif same_looks:
                for n in same_looks[:1] if len(same_looks) == 1 else []:
                    unexplained_new.remove(n)
                if len(same_looks) == 1:
                    n = same_looks[0]
                    if names_related(game, old.name, n.name):
                        self.note("name", f"related|{old.key}|{n.name}",
                                  f"{old.name} is {n.name} from {b.label} on ({old.looks()}): a last name or a "
                                  "numeral given or dropped, or a name the Villager Details screen cut.")
                        continue
                    if any(what == "Name" and o == old.name and nn == n.name
                           for _who, what, o, nn in self.logs.event_changes):
                        self.note("name", f"event|{old.key}|{n.name}",
                                  f"{old.name} is {n.name} from {b.label} on ({old.looks()}): an island event "
                                  "renamed them (the Island Events log).")
                        continue
                    self.rename_question(old, n, a.label, b.label, self.name_record(old, n))
                else:
                    self.ask("lost", f"lost|{old.key}|{a.when}",
                             f"{old.described()} is in {a.label} but not in {b.label}, with no Death, Disappeared, "
                             f"Left the tribe or Unaccounted record; {len(same_looks)} villagers new in {b.label} have "
                             f"the same looks ({', '.join(n.name for n in same_looks)}). Which one is {old.name}, if "
                             "any?", [f"{KEEP} (left or died without a record)"] + [n.name for n in same_looks])
            else:
                plain_lost.append(old)
        if len(plain_lost) >= 4:
            # Many at once (a log begun after they went, a restored save...): one question, every name.
            names = ", ".join(s.described() for s in plain_lost[:20])
            more = f" and {len(plain_lost) - 20} more" if len(plain_lost) > 20 else ""
            self.ask("lost", f"lost-many|{a.when}|{b.when}|{len(plain_lost)}",
                     f"{len(plain_lost)} villagers are in {a.label} but not in {b.label}, and no Death, Disappeared, "
                     f"Left the tribe or Unaccounted record says what became of them: {names}{more}. Possibly "
                     f"lost{restore_why}.",
                     [f"{KEEP} (they left or died without a record)"])
            plain_lost = []
        for old in plain_lost:
            self.ask("lost", f"lost|{old.key}|{a.when}",
                     f"{old.described()} is in {a.label} but not in {b.label}, and no Death, Disappeared, Left "
                     f"the tribe or Unaccounted record says what became of them: possibly lost{restore_why}.",
                     [f"{KEEP} (they left or died without a record)"])
        for n in [] if restored else unexplained_new:
            if n.key in self.recorded or (b.kind == "history" and a.kind != "history"):
                continue
            if n.age is not None and n.age < 3 * 20 and self.game == 1:
                continue                                    # a child just become its own record (2 years)
            self.note("new", f"new|{n.key}|{b.when}",
                      f"{n.described()} appears first in {b.label} (not in {a.label}) with no Birth, Arrived or "
                      "island event record of that name and looks.")

    def rename_question(self, old: Seen, new: Seen, where_old: str, where_new: str,
                        record: Record | None, birth: Record | None = None) -> None:
        said = birth.heading if birth is not None else where_old
        how = (f"A \"Name changed\" record ({record.path.name}) says the name changed in the game, from {old.name} "
               f"to {new.name}; did you rename this villager? (The Villager Details screen can copy one villager's "
               "name onto another.)" if record is not None else "No log records a rename.")
        text = (f"{said} says {old.name}; {where_new} says {new.name} ({new.looks()}"
                f"{', age ' + str(new.age) if new.age is not None else ''}). {how} Which is right?")
        self.ask("rename", f"rename|{old.name}|{new.head}|{new.body}|{new.name}", text,
                 [f"{KEEP}: {new.name} is right (I renamed them)", f"{old.name} is right (give the name back)"],
                 rename=(new.key, old.name))

    # -- records against the save ----------------------------------------------------------------
    def births_against(self, living: list[Seen], label: str) -> None:
        """A living villager with no Birth or Arrived record of their own name and looks, whose looks,
        sex, likes, dislikes and parents are those of a Birth record under ANOTHER name that nobody
        alive carries with those looks and no departure explains: asked (the owner's Iruwa Okelani)."""
        alive = {s.key for s in living}
        for v in living:
            if v.key in self.recorded:
                continue
            found = []
            for r in self.logs.births:
                c = r.who
                if (c.head, c.body) != (v.head, v.body) or c.name == v.name or c.key in alive \
                        or c.key in self.departed or names_related(self.game, c.name, v.name):
                    continue
                if c.sex and v.sex and c.sex != v.sex:
                    continue
                if not (_compatible(c.likes, v.likes) and _compatible(c.dislikes, v.dislikes)):
                    continue
                if self.game != 1 and not (_same_parent(c.father, v.father) and _same_parent(c.mother, v.mother)):
                    continue
                found.append(r)
            twins = [w for w in living if w is not v and (w.head, w.body) == (v.head, v.body)
                     and (w.father, w.mother) == (v.father, v.mother) and w.key not in self.recorded]
            if len(found) == 1 and not twins:
                r = found[0]
                self.rename_question(r.who, v, r.heading, label,
                                     next((n for n in self.logs.names_changed
                                           if n.extra.get("old") == r.who.name and n.who.name == v.name), None),
                                     birth=r)

    # -- files -----------------------------------------------------------------------------------
    def files(self, living: list[Seen], saves: list[tuple[Path, list[Seen]]]) -> None:
        folder = Path(self.folder)
        copies_root = folder / layout.DATA / layout.COPIES
        repairs: list[tuple[datetime | None, list[str]]] = []
        for root in [folder / layout.LOGS, folder / "VVFP Logs"] + [
                folder / layout.save_root(s) / layout.SAVE_LOGS for s in layout.SLOTS]:
            if not root.is_dir():
                continue
            for p in root.rglob("*.txt"):
                if p.parent.name in ("Repairs", layout.REPAIRS_LOGS):
                    try:
                        repairs += _repair_entries(p.read_bytes().decode("latin-1"))
                    except OSError:
                        pass
        for path in self.logs.files:
            try:
                data = path.read_bytes()
            except OSError as exc:
                self.ask("file", f"unreadable|{path.name}", f"{_rel(folder, path)} could not be read ({exc}).",
                         [f"{KEEP}"])
                continue
            text = data.decode("latin-1")
            if data and not text.endswith("\n"):
                self.ask("file", f"cut|{_answer_place(folder, _rel(folder, path))}|{len(data)}",
                         f"{_rel(folder, path)} ends in the middle of a line: it may have been cut short "
                         "(the patcher writes every record whole).", [f"{KEEP} (it is complete)"])
            count = _record_count(text)
            # REPAIR BY REPAIR (review of #585).  Each copy is the file just before one repair; the next
            # copy (or the file now) is it after that repair and the records written since, which only
            # ever add.  So each step may lose only what THAT repair's own Repairs-log entry took out of
            # THIS file -- never the sum of every repair of a file of that name, which let a later loss
            # hide behind an earlier repair's count.
            rel = _rel(folder, path)
            place = _answer_place(folder, rel)
            chain: list[tuple[Path | None, int, datetime]] = []
            for copy in sorted(_copies_of(path, copies_root, folder), key=lambda p: p.stat().st_mtime):
                try:
                    chain.append((copy, _record_count(copy.read_bytes().decode("latin-1")),
                                  datetime.fromtimestamp(copy.stat().st_mtime)))
                except OSError:
                    continue
            chain.append((None, count, datetime.max))
            for (copy, old_count, made), (later, new_count, until) in zip(chain, chain[1:]):
                if old_count <= new_count:
                    continue
                removed = _removed_by_repair(repairs, rel, path.name, made, until)
                where = rel if later is None else f"the later copy {later.name}"
                if new_count + removed >= old_count:
                    self.note("file", f"shrunk-ok|{place}|{copy.name}",
                              f"{where} holds {old_count - new_count} record(s) fewer than the copy {copy.name} "
                              f"kept before a repair; the Repairs log says that repair took {removed} out of it.")
                else:
                    self.ask("file", f"shrunk|{place}|{copy.name}|{new_count}",
                             f"{where} holds {new_count} record(s), but the copy kept before a repair, "
                             f"{copy.name}, holds {old_count}; the Repairs log accounts for {removed} taken out of "
                             f"{path.name} by that repair. {old_count - new_count - removed} record(s) may be lost.",
                             [f"{KEEP} (I know why)"])
        # A file the patcher kept copies of, now missing -- anywhere under the patcher's folders (a file
        # an upgrade moved into its own subfolder is not missing, src/vv_save_layout.py).
        present: set[str] = set()
        copies: dict[str, list[Path]] = {}
        # The older layout's folders, then the saves' own "Virtual Villagers Fun Patcher\Save <S>" (its Logs,
        # its Data and its own Copies Made Before Repairs).
        own_copies = {folder / layout.save_root(s) / layout.SAVE_DATA / layout.COPIES for s in layout.SLOTS}
        for top in (layout.LOGS, layout.DATA, "VVFP Logs", layout.SAVES):
            root = folder / top
            if not root.is_dir():
                continue
            for p in root.rglob("*"):
                if not p.is_file():
                    continue
                if ".before-" in p.name:
                    # A copy kept before a repair: beside the file (older builds) or in Copies Made Before
                    # Repairs at the file's own place (review of #585: that tree was skipped, so a file
                    # whose only copy is there went missing unnoticed).
                    copies.setdefault(_file_key(p, p.name.split(".before-", 1)[0]), []).append(p)
                elif copies_root not in p.parents and not own_copies.intersection(p.parents):
                    present.add(_file_key(p, p.name))
        # By name AND slot (review of #585): the slot folders reuse names ("Village History 1.txt" under
        # Save 1 and Save 2), so Save 1's file deleted while Save 2's remains is still missing.  Any other
        # folder of the same slot counts, as an upgrade may move a data file into its own subfolder.
        for key, kept in sorted(copies.items(), key=lambda item: (item[0][0], item[0][1] or 0)):
            name, slot = kept[0].name.split(".before-", 1)[0], key[1]
            original = kept[0].with_name(name)
            if key in present or not self.slot_file_of(original):
                continue
            named = slot is not None and f"save {slot}" in name.lower()
            where = f" (Save {slot})" if slot is not None and not named else ""
            self.ask("file", f"missing|{name}" + (f"|Save {slot}" if where else ""),
                     f"{name}{where} is missing from the patcher's folders, though the patcher kept {len(kept)} "
                     f"copy(ies) of it ({', '.join(sorted(p.name for p in kept)[:3])}): it may have been deleted or "
                     "moved, and what it held may be lost.", [f"{KEEP} (I removed it)"])
        # The save older than its own previous generation, or than the logs.
        if len(saves) >= 2:
            current = saves[-1]
            for older_path, older in saves[:-1]:
                behind = _behind(older, current[1])
                if behind:
                    self.ask("file", f"older-save|{older_path.name}",
                             f"The save {current[0].name} is older than the game's earlier copy {older_path.name}: "
                             f"{behind} villager(s) are younger in it. It may have been replaced by an older copy (a restored backup).",
                             [f"{KEEP} (I restored it)"])
        last = [c for c in self.logs.censuses if c.kind == "history"]
        if last and saves:
            current_path, current = saves[-1]
            snap = last[-1]
            behind = _behind(snap.people, current)
            if behind and snap.when > _when(current_path):
                self.ask("file", f"save-behind-logs|{snap.when}",
                         f"The save {current_path.name} ({_when(current_path)}) is older than the latest Village "
                         f"History snapshot ({snap.when}): {behind} villager(s) are younger in the save. It may have "
                         "been replaced by an older copy (a restored backup), or the game did not save at its last "
                         "quit (Alt-F4 closes it without saving).",
                         [f"{KEEP} (I restored it)"])

    def titles(self, living: list[Seen], bodies: list[Seen] | None = None) -> None:
        """The Custom Titles file against the save and the latest History snapshot.

        A PENDING title (v1.35.70): after a load the game could not tell which villager it belongs to --
        two could be them, or none -- so it is kept, shown on nobody, and never dropped for it.  Each one
        is a question naming the title, the identity it is kept by and the villagers who could be them.

        A custom title the latest History snapshot gives a villager still alive, with no entry for them in
        the file (bound or pending): possibly lost (an entry dropped, or the file lost or replaced)."""
        import vv_titles_file as titles_file
        path = layout.route(Path(self.folder), f"{layout.DATA}\\Custom Titles\\Custom Titles - Save {self.slot}.dat")
        try:
            got = titles_file.read(path.read_bytes(), self.game)
        except OSError:
            got = None
        file_entries = got[1] if got else []
        history = [c for c in self.logs.censuses if c.kind == "history"]
        present = list(living) + list(bodies or [])
        for k, e in enumerate(file_entries):
            if e.pending:
                self._pending_title(path, e, present, history[-1].people if history else [], living, file_entries,
                                    k)
        if not history:
            return
        titled = [s for s in history[-1].people if s.title and s.title.lower() not in ("none", "(none)")]
        if not titled:
            return
        # HOW MANY entries of each (identity, title) the file holds -- counted, never a set (v1.35.71 v2,
        # review of #586): two villagers of one identity (twins) may each have a title of their own (review
        # of #585), and may each have the SAME title text; a set kept one (identity, title) for both, so
        # losing one of their two entries was never reported.
        held = Counter((e.identity, e.title) for e in file_entries)
        needed: Counter = Counter()
        names: dict[tuple, list[str]] = {}
        by_key: dict[tuple, list[Seen]] = {}
        for s in history[-1].people:
            by_key.setdefault(s.key, []).append(s)
        for key, snap in by_key.items():
            mine = [s for s in snap if any(s is t for t in titled)]
            if not mine:
                continue
            now = [v for v in living if v.key == key]
            ids = {v.title_id for v in now}
            # Who they are now must be told apart: the snapshot's villagers of that name and looks are the
            # save's (no newcomer among them), and all of one title identity.
            if not now or len(now) > len(snap) or len(ids) != 1 or None in ids:
                continue
            identity = ids.pop()
            gone = len(snap) - len(now)     # at most this many of them died or left since the snapshot
            for title, count in Counter(s.title for s in mine).items():
                # Each title the snapshot gives them, less any who may have gone; one still alive keeps
                # theirs (as before v1.35.71 v2, when only one of that name and looks is alive).
                need = max(count - gone, 1 if len(now) == 1 else 0)
                if need:
                    needed[(identity, title)] += need
                    names.setdefault((identity, title), []).extend(s.name for s in mine if s.title == title)
        lost = []
        for (identity, title), need in needed.items():
            if held[(identity, title)] < need:
                who = ", ".join(dict.fromkeys(names[(identity, title)]))
                short = need - held[(identity, title)]
                lost.append(f"{who} (\"{title}\")" if need == 1 else
                            f"{who} (\"{title}\": {need} villagers have it, the file holds {held[(identity, title)]}, "
                            f"so {short} entr{'y is' if short == 1 else 'ies are'} missing)")
        if lost:
            self.ask("titles", f"titles|{history[-1].when}|{'|'.join(lost)}",
                     f"The Village History snapshot of {history[-1].when} gives {len(lost)} living villager(s) a custom "
                     f"title the Custom Titles file ({path.name}) no longer holds for them: {', '.join(lost)}. The "
                     "title(s) may be lost.", [f"{KEEP} (I removed the title)"])

    def _pending_title(self, path: Path, e, present: list[Seen], snapshot: list[Seen],
                       living: list[Seen] | None = None, file_entries: list | None = None,
                       place: int | None = None) -> None:
        """One question for one pending title: which title, the identity it is kept by, and who could be
        them now (the villagers the game itself would weigh: the same name and likes, then the whole
        identity).  `place` is the entry's place in the file: two entries may wait with the same identity
        and title (two villagers of one identity, each given that title), and each is its own question."""
        import vv_last_names as ln
        import vv_titles_file as titles_file
        file_entries = list(file_entries or [e])
        if place is None:
            place = next(k for k, x in enumerate(file_entries) if x is e)
        same = [x for x in file_entries if x.pending and x.identity == e.identity and x.title == e.title]
        raw = titles_file.entry_bytes(e)
        carriers = [v for v in present if v.title_id == e.identity]
        could = [v for v in carriers if v.title_looks is not None and titles_file.could_be(self.game, e, v.title_looks)]
        named = [s.name for s in snapshot if s.title == e.title]
        name = carriers[0].name if carriers else (named[0] if len(set(named)) == 1 else None)
        if e.known:
            sex = "male" if e.sex == ln.FIELDS[self.game].male else "female"
            skills = ", ".join(f"{s:g}" for s in e.skill_values(self.game, rounded=True))
            kept = (f"{name or 'a villager whose name the file does not keep'} (the name, likes and dislikes the "
                    f"file's identity {e.identity:08X} holds; head {e.head}, body {e.body}, {sex}, age at least "
                    f"{e.age} units, skills at least {skills})")
        else:
            kept = (f"{name or 'a villager whose name the file does not keep'} (the name, likes and dislikes the "
                    f"file's identity {e.identity:08X} holds; an older file, so no looks are kept with it)")
        if could:
            who = "; ".join(f"{v.described()}{'' if v.rank is None else f', record {v.rank}'}" for v in could)
            whom = f"{len(could)} villager(s) in the save could be them: {who}."
        else:
            whom = "No villager in the save has that whole identity now (they may have died, or their looks changed)."
        others = [v for v in carriers if v not in could]
        if others:
            whom += (" Not them (the same name and likes, another head, body or sex, or younger or less skilled): "
                     + "; ".join(v.described() for v in others) + ".")
        if e.contested:
            after = ("While it waited, two or more villagers could be them at once, so the game will NOT give it "
                     "back by itself, even if only one of them is left now (the others died or left): which one "
                     "had it can not be told, and it is never guessed. If it is theirs, say so below (or give it to "
                     "them again with the Custom Island Event's title); until then it waits.")
            if len(could) == 1:
                after = f"The one left who could be them: {could[0].name}. " + after
        else:
            after = ("The game gives it back by itself once exactly one villager has that whole identity; until "
                     "then it waits.")
        # THE PLAYER'S ANSWER SETTLES IT (v1.35.71).  Give it to one of the villagers who could be them --
        # living, in the save now, and holding no other title -- or remove it; Repair Saves & Logs then
        # changes the Custom Titles file (settle_titles).  "Keep as is" leaves it waiting.  Never a guess:
        # only a villager the player names, and only one the game itself would weigh as them.
        claimed = {x.index for x in file_entries if not x.pending}
        options = [f"{KEEP} (leave it waiting)"]
        actions: dict[str, TitleAction] = {}
        which = dict(entry=place, raw=raw, twins=len(same))
        for v in could:
            if v not in (living or []) or v.record is None or v.at is None or v.record in claimed:
                continue
            option = (f"Give it to {v.described()}{'' if v.rank is None else f', record {v.rank}'} (it is theirs)")
            if option in actions:
                continue
            actions[option] = TitleAction("bind", e.identity, e.title, v.name, v.at, v.record,
                                          dict(v.title_looks or {}), **which)
            options.append(option)
        clear = "Remove the title (it is nobody's now)"
        actions[clear] = TitleAction("clear", e.identity, e.title, **which)
        options.append(clear)
        if len([a for a in actions.values() if a.kind == "bind"]) >= 2:
            after += (" If two of them still have the same name, likes, head, body and sex and neither is younger "
                      "or less skilled than the other, the game can not tell them apart after a load and the title "
                      "waits again.")
        qid, one_of = f"title-pending|{e.identity:08X}|{e.title}", ""
        if len(same) > 1:
            # Two or more entries wait with this identity and title (v1.35.71 v2, review of #586): one
            # question for EACH, so the player can answer for one of them.  Its id holds the entry's own
            # bytes (a checksum) and which of the byte-identical ones it is, so a kept answer stays with it.
            alike = [x for x in same if titles_file.entry_bytes(x) == raw]
            n = next(k for k, x in enumerate(alike, 1) if x is e)
            qid += f"|{zlib.crc32(raw):08X}#{n}"
            one_of = (f" This is entry {place + 1} of the file, one of {len(same)} pending entries of that title "
                      "kept for that identity (two villagers of one name, likes and dislikes were each given it); "
                      "each has its own question, and an answer changes only its own entry.")
        self.ask("titles", qid,
                 f"The custom title \"{e.title}\" is PENDING in {path.name}: after a load the game could not tell "
                 f"which villager it belongs to, so it is kept, shown on nobody -- never dropped. It is kept for "
                 f"{kept}.{one_of} {whom} {after} Your answer changes the file only in Repair Saves & Logs, with "
                 "the game closed and a backup first.", options, title_actions=actions)
    def slot_file_of(self, path: Path) -> bool:
        """Whether a file belongs to this game and slot (or to the game's shared logs)."""
        name = path.name
        folder_slot = layout.is_slot_folder(path)
        if folder_slot is not None:
            return folder_slot == self.slot     # the slot's own folder: every file in it is the slot's
        if f"Save {self.slot}" in name:
            return f"Virtual Villagers {self.game} " in name or "Virtual Villagers " not in name
        return name.startswith(f"Virtual Villagers {self.game} ") and layout.is_slot_folder(path) in (None, self.slot)


def _rel(folder: Path, path: Path) -> str:
    try:
        return str(path.relative_to(folder))
    except ValueError:
        return str(path)


FILE_QUESTIONS = ("cut", "shrunk", "shrunk-ok")       # the file questions whose id holds the file's place


def _answer_place(folder: Path, rel: str) -> str:
    """The place a file question's id names a file by (relative to the save folder), the same before
    and after Move Files to Save Folders: a file of a save still in the older folders by its place in
    the save's own folder ("Virtual Villagers Fun Patcher\\Save <n>\\..."), where the move puts it.  Not
    when both places hold a file (the move leaves both, and each is its own file): then each is named
    by where it is, so an answer about one is never applied to the other."""
    place = layout.per_save_place(rel)
    if place is None:
        return rel
    new = place[1].replace("\\", os.sep)
    if not (Path(folder) / rel).exists() or not (Path(folder) / new).exists():
        return new
    return rel


def _answer_id(folder: Path, qid: str) -> str:
    """A remembered file question's id with its file named as _answer_place names it now (an answer
    given before the move, or before this build keyed it so, still holds after it)."""
    topic, bar, rest = qid.partition("|")
    if topic not in FILE_QUESTIONS or not bar:
        return qid
    rel, bar, tail = rest.partition("|")
    return f"{topic}|{_answer_place(folder, rel)}{bar}{tail}"


def _copies_of(path: Path, copies_root: Path, folder: Path) -> list[Path]:
    """The copies kept of a log before repairs, newest first: beside it, and in Copies Made Before
    Repairs under the same relative place."""
    found = [p for p in path.parent.glob(path.name + ".before-*") if p.is_file()]
    try:
        relative = path.relative_to(folder)
        older = layout.older_layout(folder, path)
        if older is not None:
            # A file of a save's own folder: its copies are in that save's own Copies Made Before
            # Repairs, at its place inside "Save <S>" (vv_log_tools.copy_before_repair), and the ones
            # made before "Move Files to Save Folders..." moved it stay at its older-layout place.
            mirrors = [folder / relative.parts[0] / relative.parts[1] / layout.SAVE_DATA / layout.COPIES
                       / Path(*relative.parts[2:]),
                       copies_root / Path(*older.split("\\"))]
        else:
            mirrors = [copies_root / relative]
        for mirror in mirrors:
            found += [p for p in mirror.parent.glob(path.name + ".before-*") if p.is_file()]
    except (ValueError, OSError):
        pass
    return sorted(found, key=lambda p: p.stat().st_mtime, reverse=True)


def _file_key(path: Path, name: str) -> tuple[str, int | None]:
    """A patcher file by name and save slot: the slot of the "...Logs\\Save <S>" folder it is in (a copy
    in Copies Made Before Repairs keeps that folder), or of the save's own "Virtual Villagers Fun
    Patcher\\Save <S>" folder it is in (its Logs, its Data, its own copies), else the "Save <S>" its name
    gives, else None."""
    slot = layout.is_slot_folder(path)
    if slot is None:
        parts = [p.lower() for p in Path(path).parts]
        for i, part in enumerate(parts[:-2]):
            m = re.fullmatch(r"save ([1-5])", parts[i + 1]) if part == layout.SAVES.lower() else None
            if m:
                slot = int(m.group(1))
                break
    if slot is None:
        m = re.search(r"\bSave ([1-5])\b", name)
        slot = int(m.group(1)) if m else None
    return name.lower(), slot


def _record_count(text: str) -> int:
    return sum(1 for line in text.replace("\r\n", "\n").split("\n") if RECORD_HEAD.match(line))


def _repair_entries(text: str) -> list[tuple[datetime | None, list[str]]]:
    """The Repairs log's entries: each "Repair N" with its "Date:" and its lines."""
    out: list[tuple[datetime | None, list[str]]] = []
    for block in re.split(r"(?m)^Repair \d+\s*$", text.replace("\r\n", "\n"))[1:]:
        lines = block.split("\n")
        when = None
        for line in lines:
            m = re.match(r"^\s*Date:\s*(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)", line)
            if m:
                when = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
                break
        out.append((when, lines))
    return out


# A copy is made in the same moment as its repair's entry; the clocks of the two may differ a little.
_REPAIR_SLACK_SECONDS = 120


def _removed_by_repair(entries: list[tuple[datetime | None, list[str]]], rel: str, name: str,
                       made: datetime, until: datetime) -> int:
    """What the repair that made a copy (at `made`) took out of THIS file: the "-- N" of its entry's
    "removed" / "taken out" lines naming the file -- its path, or its bare name in an entry written
    before paths were given -- from entries dated from `made` up to the next copy (`until`)."""
    total = 0
    for when, lines in entries:
        if when is None:
            continue
        seconds_after = (when - made).total_seconds()
        if seconds_after < -_REPAIR_SLACK_SECONDS:
            continue
        if until != datetime.max and (when - until).total_seconds() >= -_REPAIR_SLACK_SECONDS:
            continue
        for line in lines:
            if not re.search(r"(taken out|removed|Removed)", line):
                continue
            names_file = rel in line or (name in line and ("\\" + name) not in line and ("/" + name) not in line)
            m = re.search(r"-- (\d+) ", line)
            if names_file and m:
                total += int(m.group(1))
    return total


def _behind(older: list[Seen], newer: list[Seen]) -> int:
    """How many villagers, matched exactly and alone on name, head and body, are younger in `newer`
    -- counted only when they are most of those matched (one restore, not one odd record)."""
    a = {}
    for s in older:
        a.setdefault(s.key, []).append(s)
    b = {}
    for s in newer:
        b.setdefault(s.key, []).append(s)
    matched = younger = 0
    for key, xs in a.items():
        ys = b.get(key, [])
        if len(xs) == 1 and len(ys) == 1 and xs[0].age is not None and ys[0].age is not None:
            matched += 1
            younger += ys[0].age < xs[0].age
    return younger if matched and younger * 2 > matched else 0


# ---------------------------------------------------------------------------
# The reconciliation
# ---------------------------------------------------------------------------

def answered(folder: Path, game: int, slot: int, villages: set[str] | None) -> dict[str, str]:
    import vv_log_decisions as decisions
    out = {}
    for d in decisions.load(folder, game, slot):
        if d.get("kind") == DECISION_KIND and isinstance(d.get("field"), str) \
                and (villages is None or d.get("village") in villages):
            out[_answer_id(folder, d["field"])] = str(d.get("verdict", ""))
    return out


def reconcile(folder: Path, game: int, slot: int) -> Reconciliation:
    """Read everything this slot's village has, follow every villager through it, and say what does
    not agree.  Nothing is written."""
    import vv_log_additions as additions
    import vv_tribe_rename
    folder = Path(folder)
    if game not in GAME_TITLES or slot not in (1, 2, 3, 4, 5):
        raise ReconcileError(f"There is no game {game} save slot {slot}.")
    villages = additions.current_villages(folder, game, slot)
    games = {g.number: g for g in vv_tribe_rename.GAMES}
    generations = save_generations(folder, game, slot)
    current_path = folder / f"{_checker().SAVE_STEMS[game]}{slot}.ldw"
    if current_path not in generations:
        raise ReconcileError(f"Save {slot} has no tribe in {folder.name} ({current_path.name} is not there).")
    try:
        village_name = vv_tribe_rename.save_name(games[game], current_path.read_bytes())
    except (OSError, KeyError, ValueError):
        village_name = None
    logs = read_logs(folder, game, slot, villages)
    b = _Builder(folder, game, slot, logs, answered(folder, game, slot, villages))
    sources: list[str] = []
    saves: list[tuple[Path, list[Seen]]] = []
    bodies_now: list[Seen] = []
    for path in generations:
        try:
            if path != current_path:
                name = vv_tribe_rename.save_name(games[game], path.read_bytes())
                if village_name and name and name != village_name:
                    b.note("save", f"other-village|{path.name}",
                           f"{path.name} (an older generation of the save) holds another village, \"{name}\": not "
                           "compared.")
                    continue
            alive, bodies = read_save(path, game)
        except (OSError, ReconcileError, KeyError, ValueError) as exc:
            if path == current_path:
                raise ReconcileError(str(exc)) from exc
            b.ask("file", f"unreadable-save|{path.name}", f"{path.name} (an older generation of the save) could not "
                  f"be read ({exc}).", [f"{KEEP}"])
            continue
        saves.append((path, alive))
        sources.append(f"{path.name} ({_when(path)}): {len(alive)} living")
        if path == current_path:
            bodies_now = bodies
    living = saves[-1][1] if saves and saves[-1][0] == current_path else []
    # The records against the save first: a Birth record's own words lead a question.
    b.births_against(living, f"the save {current_path.name}")
    # The game's own generations of the save, oldest to newest.
    for (pa, a), (pb, bb) in zip(saves, saves[1:]):
        b.compare(Census(f"the save copy {pa.name} ({_when(pa)})", _when(pa), "save", a, pa),
                  Census(f"the save {pb.name} ({_when(pb)})" if pb == current_path else
                         f"the save copy {pb.name} ({_when(pb)})", _when(pb), "save", bb, pb),
                  bodies_now if pb == current_path else None)
    # The History snapshots in order, then the latest snapshot against the save.
    history = [c for c in logs.censuses if c.kind == "history"]
    if history:
        sources.append(f"{len(history)} Village History snapshot(s), {history[0].when} to {history[-1].when} "
                       f"({len(history[-1].people)} villagers in the latest)")
    for c in logs.censuses:
        if c.kind != "history":
            sources.append(f"{c.label}: {len(c.people)} villagers")
    # The rosters in time order -- the History snapshots and the Village Population page (review of #585:
    # the page was read and never compared, so a villager, a like, a parent or the looks only it still
    # held could be lost from the save unasked) -- then the latest of them against the save.
    rosters = sorted(history + [c for c in logs.censuses if c.kind == "population"], key=lambda c: c.when)
    for a, c in zip(rosters, rosters[1:]):
        b.compare(a, c)
    if rosters and living:
        snap = rosters[-1]
        now = Census(f"the save {current_path.name} ({_when(current_path)})", _when(current_path), "save", living,
                     current_path)
        # A save older than the latest snapshot (restored with its time kept) is compared too (review of
        # #585): a villager, a like, a parent or the looks the restore lost are asked about.
        b.compare(snap, now, bodies_now, restored=snap.when > now.when)
    sources.append(f"{len(logs.births)} Birth, {len(logs.arrivals)} Arrived, {len(logs.departures)} Death / "
                   f"Disappeared / Left / Unaccounted, {len(logs.looks_changed)} Appearance changed, "
                   f"{len(logs.names_changed)} Name changed record(s); {len(logs.files)} log file(s)")
    for r in logs.names_changed:
        # Every name change the game made in play, asked about even when a roster above shows nothing
        # (the change may predate the History log): recorded, never hidden.
        old = Seen(r.extra.get("old", ""), r.who.head, r.who.body)
        if any(f.rename and f.rename[1] == old.name and f.rename[0][0] == r.who.name for f in b.findings.values()):
            continue
        b.rename_question(old, r.who, r.heading, f"the {r.path.name}", r)
    b.files(living, saves)
    b.titles(living, bodies_now)
    if b.slot_reused or b.slot_moved:
        b.note("slots", "slot-reuse", f"Record slots: {b.slot_reused} hold another villager than in an earlier "
               f"generation of the save, and {b.slot_moved} villager(s) are in another slot -- deaths free slots "
               "that later villagers take and every load packs the records (normal, above all at the 256 cap). "
               "Everything here follows villagers by who they are, never by the slot.")
    _vv1_roster_reuse(b, folder, game, slot, living)
    followed = len({s.key for c in logs.censuses for s in c.people} | {s.key for _p, a in saves for s in a})
    return Reconciliation(folder, game, slot, village_name, list(b.findings.values()), sources, followed)


def _vv1_roster_reuse(b: _Builder, folder: Path, game: int, slot: int, living: list[Seen]) -> None:
    """A New Home's Parentage Records keep a roster of the villager in each record slot: the slots
    that now hold someone else (after deaths and packing) are a NOTE -- the companion follows each
    entry to its villager by identity."""
    if game != 1:
        return
    import vv1_parents_restore as restore
    try:
        table = restore.read_table(restore.parents_path(folder, slot), slot)
    except (OSError, ValueError, AttributeError, restore.RestoreError):
        return
    if table is None:
        return
    moved = 0
    for v in living:
        ident = table.identity(v.rank) if v.rank is not None and v.rank < restore.COUNT else None
        if ident is not None and ident[0] != v.name:
            moved += 1
    if moved:
        b.note("slots", "vv1-roster", f"Parentage Records: {moved} record slot(s) hold another villager than when "
               "the file was last written (deaths, births into freed slots, a load that packed the records); its "
               "entries follow each villager by identity, never by the slot.")


# ---------------------------------------------------------------------------
# Writing: the report, and the player's answers
# ---------------------------------------------------------------------------

def report_path(folder: Path, game: int, slot: int) -> Path:
    """The save's own "Virtual Villagers Fun Patcher\\Save <n>\\Logs\\Reconciliation" folder, always: the
    report is written whole each time (no history to keep together), so an older report left in
    "...Logs\\Save <n>\\Reconciliation" is never added to and never kept in use."""
    return layout.own_slot_log_folder(Path(folder), REPORT_FOLDER, slot) / REPORT_NAME.format(game=game, slot=slot)


def export(rec: Reconciliation) -> Path:
    """Write the report (the only file this module writes): through a temporary file moved into place."""
    target = report_path(rec.folder, rec.game, rec.slot)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_bytes(rec.render().replace("\n", "\r\n").encode("latin-1", "replace"))
    os.replace(temporary, target)
    return target


def kind(folder: Path, game: int, slot: int, rec: Reconciliation | None = None):
    """The questions for Repair Saves & Logs' checklist (src/vv_log_additions.py Kind): one per
    contradiction, "Don't know (leave it)" first, so nothing changes unless the player says so."""
    import vv_log_additions as additions
    out = additions.Kind("reconcile", "Contradictions the read-only reconciliation found (asked; nothing "
                                      "changes without your answer)")
    try:
        rec = rec or reconcile(folder, game, slot)
    except (ReconcileError, OSError) as exc:
        out.notes.append(f"The reconciliation could not run: {exc}")
        return out
    for n, f in enumerate(rec.questions, 1):
        out.questions[f.qid] = additions.Question(f.qid, f"{n}. {f.text}", list(f.options), DONT_KNOW)
    out.context = {"game": game, "slot": slot, "renames": {f.qid: f.rename for f in rec.questions if f.rename},
                   "titles": {f.qid: f.title_actions for f in rec.questions if f.title_actions}}
    if rec.questions:
        out.notes.append(f"{len(rec.questions)} contradiction(s) between the save, its older copies, the logs and "
                         "the patcher's files. Answer them with the button below; \"Don't know (leave it)\" "
                         "changes nothing and asks again next time.")
    return out


def give_names_back(folder: Path, game: int, slot: int, renames: dict[tuple, str], controller,
                    now: datetime | None = None) -> dict[tuple, str]:
    """The answer "<the record's name> is right (give the name back)": each villager ((name, head, body)
    now) gets that name back everywhere, as Repair's other renames do (src/vv_last_names.py: the save,
    the logs and the patcher's files; refused while the game runs; a backup first; every file put back
    on a failure).  Returns what was renamed."""
    import vv_last_names as ln
    import vv_log_tools as tools
    try:
        work = ln.plan_renames(Path(folder), game, slot, dict(renames), None, dead=False, ask=False)
        if not work.renames:
            return {}
        ln.apply(Path(folder), work, controller, now, ln.BACKUP_LABEL, "giving the names back")
    except (ln.LastNamesError, OSError, ValueError, struct.error) as exc:
        raise tools.LogToolError(f"The name(s) could not be given back ({exc}).") from exc
    return dict(work.renames)


TITLE_COPY_SUFFIX = ".before-title-answer"
TITLE_BACKUP_LABEL = "(before settling custom titles)"


def settle_titles(folder: Path, game: int, slot: int, actions: list[TitleAction], controller,
                  backup_folder: Path | None = None, now: datetime | None = None) -> list[str]:
    """The player's answers to pending-title questions, carried out in the Custom Titles file
    (native/shared/custom_titles.h; src/vv_titles_file.py): "Give it to <villager>" binds the PENDING
    entry to that villager's record with their looks now (no longer contested: the player said whose it
    is); "Remove the title" takes the entry out.  Every other entry stays as it was.

    Nothing is guessed and nothing stale is written: refused while the game runs (its companion keeps
    the table in memory and would write over the file); every answer is checked again against the file
    and the save as they are NOW -- the very entry the question was about (TitleAction.entry/raw/twins:
    still pending at that place, byte for byte, with as many entries of that identity and title);
    the villager still at that place in the save, alive, with that name, identity and looks, one the
    game itself would weigh as them, and holding no other title -- else nothing is changed.  A backup
    of the save folder first (`backup_folder`, Repair's own, else one made here), the file as it was
    kept in Copies Made Before Repairs, a write through a temporary file moved into place and read
    back, and one "Repair <n>" record in the Repairs Made log.  Returns the lines for Repair's own
    record.  Raises vv_log_tools.LogToolError (nothing changed) on any refusal or failure."""
    import vv_last_names as ln
    import vv_log_tools as tools
    import vv_lost_titles as lt
    import vv_save_backup
    import vv_titles_file as titles_file
    folder = Path(folder)
    if not actions:
        return []
    tools._refuse_if_running(folder, controller)
    path = layout.route(folder, lt.TITLES_FILE.format(slot=slot))
    try:
        original = path.read_bytes()
        got = titles_file.read(original, game)
        data = ln.save_path(folder, game, slot).read_bytes()
        living = set(ln._entries(game, data))
    except (OSError, ln.LastNamesError, ValueError, struct.error) as exc:
        raise tools.LogToolError(f"The custom titles could not be read ({exc}); nothing was changed.") from exc
    if got is None:
        raise tools.LogToolError(f"{path.name} is not a titles file this game reads; nothing was changed.")
    version, entries = got
    f = ln.FIELDS[game]
    done: list[str] = []
    # Every answer is matched to ITS entry in the file as it is now, before anything changes (v1.35.71 v2,
    # review of #586): two entries may wait with one identity and title, so an entry is the one at the
    # place the question saw, still pending, byte for byte as it was, with as many such entries as then.
    # Anything else -- the file changed since -- changes nothing, and the question is asked again.
    resolved: list = []
    for a in actions:
        mine = [e for e in entries if e.pending and e.identity == a.identity and e.title == a.title]
        if a.entry is None:
            e = mine[0] if len(mine) == 1 else None
        else:
            e = entries[a.entry] if 0 <= a.entry < len(entries) else None
            if e is None or not any(e is x for x in mine) or len(mine) != a.twins \
                    or titles_file.entry_bytes(e) != a.raw:
                e = None
        if e is None:
            raise tools.LogToolError(f"\"{a.title}\" is no longer waiting in {path.name} as the question saw it "
                                     "(the game or another repair changed it); nothing was changed.")
        if any(e is x for _a, x in resolved):
            raise tools.LogToolError(f"Two answers were given for one pending entry of \"{a.title}\"; nothing was "
                                     "changed.")
        resolved.append((a, e))
    for a, e in resolved:
        if a.kind == "clear":
            entries[:] = [x for x in entries if x is not e]
            done.append(f"Removed the pending custom title \"{a.title}\" (identity {a.identity:08X})")
            continue
        try:
            here = a.at is not None and a.at in living \
                and data[a.at:a.at + f.name_cap].split(b"\0", 1)[0].decode("latin-1") == a.name \
                and ln._title_identity(data, a.at, f) == a.identity \
                and lt._record_index(game, data, a.at) == a.record
            looks = titles_file.looks_from_save(game, data, a.at) if here else None
        except (ValueError, IndexError, struct.error):
            here, looks = False, None
        if not here or looks != a.looks:
            raise tools.LogToolError(f"{a.name} is no longer in the save as the question saw them (the save "
                                     f"changed since); \"{a.title}\" was not given and nothing was changed.")
        if not titles_file.could_be(game, e, looks):
            raise tools.LogToolError(f"{a.name} is not someone the title \"{a.title}\" could belong to (another "
                                     "head, body or sex, or younger or less skilled); nothing was changed.")
        if any(not x.pending and x.index == a.record for x in entries):
            raise tools.LogToolError(f"{a.name} (record {a.record}) already has a custom title in {path.name}; "
                                     f"\"{a.title}\" was not given and nothing was changed.")
        e.index, e.known, e.contested = a.record, True, False
        for key, value in looks.items():
            setattr(e, key, value)
        done.append(f"Gave the pending custom title \"{a.title}\" to {a.name} (record {a.record})")
    # The file's own version, every other entry as it was; a pending entry exists only in version 3.
    updated = titles_file.serialise(game, entries, version)
    if titles_file.read(updated, game) is None:
        raise tools.LogToolError(f"{path.name} would not be a file the game reads; nothing was changed.")
    if backup_folder is None:
        try:
            backup_folder = vv_save_backup.copy_save_folder(folder, now or datetime.now(),
                                                            suffix=TITLE_BACKUP_LABEL).backup_folder
        except vv_save_backup.BackupError as exc:
            raise tools.LogToolError(f"The backup failed, so nothing was changed. {exc}") from exc
    tools._refuse_if_running(folder, controller)
    for k in range(1, 1000):
        copy = tools.copy_before_repair(folder, path, TITLE_COPY_SUFFIX + ("" if k == 1 else f"-{k}"))
        if not copy.exists():
            break
    else:
        raise tools.LogToolError(f"{path.name} has too many copies already; nothing was changed.")
    try:
        if path.read_bytes() != original:
            raise tools.LogToolError(f"{path.name} changed while the answers were being carried out; nothing "
                                     "was changed.")
        copy.parent.mkdir(parents=True, exist_ok=True)
        with open(copy, "xb") as handle:
            handle.write(original)
        ln._write(path, updated)            # a temporary file moved into place, then read back
    except (OSError, ln.LastNamesError) as exc:
        try:
            if path.read_bytes() != original:
                ln._write(path, original)
        except (OSError, ln.LastNamesError) as undo_exc:
            raise tools.LogToolError(f"{path.name} could not be written ({exc}) nor put back ({undo_exc}); your "
                                     f"backup is in {backup_folder}.") from exc
        raise tools.LogToolError(f"{path.name} could not be written ({exc}); it was put back as it was. A "
                                 f"backup is in {backup_folder}.") from exc
    try:
        import vv_tribe_rename
        games = {g.number: g for g in vv_tribe_rename.GAMES}
        name = vv_tribe_rename.save_name(games[game], data)
        header = vv_tribe_rename.village_header(name, slot) if name else None
    except (KeyError, ValueError):
        header = None
    try:
        record_path, text = tools.repair_record_start(folder, game, header or "Village: (all villages in this "
                                                      "save folder)", slot, now)
        text += "  Checked: the pending custom titles, against your answers to the reconciliation\r\n"
        for line in done:
            text += f"  {line}\r\n"
        text += f"  File: {path.relative_to(folder)} -- copy kept: {copy.name}\r\n"
        text += f"  Backup: {Path(backup_folder).name}\r\n\r\n"
        with open(record_path, "ab") as log:
            log.write(text.encode("latin-1", "replace"))
    except OSError:
        pass                                # the change stands; the reconciliation still sees it
    return done


def remember(folder: Path, game: int, slot: int, kinds: list, answers: dict[str, str],
             now: datetime | None = None, give_back=None, settle=None) -> tuple[list[str], dict[tuple, str]]:
    """Keep the player's answers (src/vv_log_decisions.py, kind "reconcile"); "Don't know" is not kept,
    so it is asked again.  Returns (lines for the Repairs log, the renames the answers asked for:
    (name, head, body) -> the name to give back -- what `give_back` returned, when it is given).

    THE RENAMES COME FIRST.  `give_back(renames)` (give_names_back) runs before any answer is kept:
    an answer once kept turns its question into an answered note, so keeping "give the name back"
    and then failing the rename (a file locked or changed) left the wrong name in place with no
    question left to retry it from.  If it raises, no answer is kept and the error goes to the
    caller; every answer is asked again."""
    import vv_log_additions as additions
    import vv_log_decisions as decisions
    rk = next((k for k in kinds if getattr(k, "id", None) == "reconcile"), None)
    if rk is None:
        return [], {}
    village = None
    villages = additions.current_villages(folder, game, slot)
    if villages:
        village = sorted(villages)[0]
        try:
            import vv_tribe_rename
            games = {g.number: g for g in vv_tribe_rename.GAMES}
            name = vv_tribe_rename.save_name(games[game], (Path(folder) / f"{_checker().SAVE_STEMS[game]}{slot}.ldw")
                                             .read_bytes())
            village = vv_tribe_rename.village_header(name, slot) if name else village
        except (OSError, KeyError, ValueError):
            pass
    entries, lines, renames, settling = [], [], {}, []
    for qid, question in rk.questions.items():
        answer = answers.get(qid)
        if not answer or answer == DONT_KNOW:
            continue
        entries.append({"kind": DECISION_KIND, "village": village, "field": qid, "verdict": answer,
                        "edited": False})
        lines.append(f"Answered: {question.text.split('. ', 1)[-1][:160]} -- {answer}")
        rename = rk.context.get("renames", {}).get(qid)
        if rename and answer.endswith("(give the name back)"):
            renames[tuple(rename[0])] = rename[1]
        action = (rk.context.get("titles", {}).get(qid) or {}).get(answer)
        if action is not None:
            settling.append(action)
    # A pending title bound or cleared (settle_titles) BEFORE the renames: it is checked against the
    # villager's name in the save as the question saw it, and a rename changes the identity it hashes.
    # Like a failed rename, a failed change keeps no answer: the question is asked again.
    if settling:
        if settle is None:
            raise ValueError("an answer that changes the Custom Titles file needs settle_titles")
        lines += settle(settling)
    if renames and give_back is not None:
        renames = give_back(renames)
    if entries:
        decisions.record(folder, game, slot, entries, now)
    return lines, renames
