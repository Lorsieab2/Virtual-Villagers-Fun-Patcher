"""Repair Saves & Logs: give back the custom titles (and New Believers' former-Heathen marks) a change
of likes or dislikes took away (all five games).

A custom title (native/shared/custom_titles.h, "Custom Titles - Save N.dat") is kept by the villager's
identity: their name, then their likes and dislikes (vv_title_identity).  The games DO change likes
and dislikes -- island events, the Custom Island Event, a vial, the Crystal of Reflections, the
Origins "Running" upgrades -- and until v1.35.68 the Story Upgrades companion then took the title
for a departed villager's and dropped it.  Seen live in The Tree of Life: "Faces in the Night" gave
Alapai new dislikes, and the Island Events log record says "  Custom title: Moon Mother -> none".
New Believers' Former Heathens file (native/shared/former_heathens.h) keys its entries by the same
identity; after such a change the entry stayed behind under the old identity, belonging to nobody.

What is restored, from the slot's own Island Events log records (native/parentage_export
WriteVillageRecord: "Island event <n>", the villager's name, head, body, likes and dislikes as the
event left them, then each change as "  <Field>: old -> new"):

  * a Custom title: a record with "Custom title: <T> -> none" AND a likes or dislikes change (the
    cause), the villager not gone and not renamed by it.  Never when a later Island Events record
    shows the title changed again (set, changed or removed on purpose), when the latest Village
    Population page shows another title, when the villager is no longer living, or when the titles
    file already gives them one.
  * New Believers: a former-Heathen entry left under the identity the villager had before their
    likes or dislikes changed.  The old likes and dislikes are rebuilt by undoing each change line
    on what the save holds now (the game's own word list, as the logs print it), newest first.

CERTAIN only when exactly one living villager has the record's name, head and body, their likes and
dislikes now read as the record says the event left them (for a title), and the rebuilt identity is
the only one possible (for a former Heathen).  Anything less is a question for the player, never a
guess (the owner's rule: ask the player on any contradiction).  What cannot be done is said in the
notes.

survey() reads only.  restore() refuses while the game runs, backs the save folder up first (Back Up
Saves' copier, BACKUP_LABEL), copies each file it changes into "Copies Made Before Repairs", keeps
every other entry byte for byte, writes each file through a temporary file and reads it back (every
file put back on a failure), and writes one "Repair <n>" record in the Repairs Made log.
"""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field
from datetime import datetime
from itertools import combinations, product
from pathlib import Path

import vv_last_names as ln
import vv_log_tools as tools
import vv_save_backup
import vv_save_layout as layout
import vv_titles_file

BACKUP_LABEL = "(before restoring lost titles)"
COPY_SUFFIX = ".before-title-restore"

TITLES_FILE = layout.DATA + "\\Custom Titles\\Custom Titles - Save {slot}.dat"
TITLE_BYTES, TITLES_MAX = vv_titles_file.TITLE_BYTES, vv_titles_file.TITLES_MAX
FORMER_FILE = layout.DATA + "\\Former Heathens\\Former Heathens - Save {slot}.dat"
FORMER_MAGIC, FORMER_VERSION, FORMER_HEADER, FORMER_ENTRY = b"VFH1", 1, 16, 8
FORMER_KINDS = {0: "blue mask", 1: "orange mask", 2: "red mask", 3: "Master (purple mask)", 4: "Chief"}

# The like and dislike words each game's exe keeps (eSayLikesList), zero-based: the lists
# native/parentage_export/parentage_export.c prints from (PREFERENCES_47 / _62 / _79_VV3 / _79;
# tests/test_lost_titles.py checks they are the same).
_W47 = ("ants,crowds,resting,laundry,medicine,turnips,butterflies,flowers,bees,the dark,caves,herbs,"
        "berries,snakes,wind,rocks,rough wood,the ocean,playing,exploring,blue,green,red,yellow,drums,"
        "bushes,bananas,coconuts,sand,sunlight,drift wood,crab meat,whale meat,fish,fruit,papaya,flies,"
        "swimming,running,dancing,monkeys,birds,work,lifting,surprises,jokes,sleeping")
_W62 = ("ants,crowds,resting,laundry,medicine,turnips,butterflies,flowers,bees,the dark,caves,herbs,"
        "berries,snakes,wind,rocks,heights,the ocean,playing,exploring,blue,green,red,yellow,drums,"
        "bushes,bananas,coconuts,sand,sunlight,wood,crab meat,whale meat,fish,fruit,papaya,flies,"
        "swimming,running,learning,dancing,monkeys,parrots,work,lifting,surprises,jokes,sleeping,"
        "jumping,cooking,fire,eating,dragonflies,owls,dreaming,children,talking,holidays,vegetables,"
        "quiet,clouds,dirt")
_W79_TAIL = ("magic,plants,rain,fog,sitting,sharks,honey,stories,coral,thunder,lightning,pearls,stars,"
             "mango,nature")
PREFERENCES = {
    1: tuple(_W47.split(",")),
    2: tuple(_W62.split(",")),
    3: tuple((_W62 + ",alchemy,potions," + _W79_TAIL).split(",")),
    4: tuple((_W62 + ",frogs,soap," + _W79_TAIL).split(",")),
    5: tuple((_W62 + ",frogs,soap," + _W79_TAIL).split(",")),
}
LIST_ROOM = 512                     # the Island Events companion's buffer for a "Likes: old -> new" side

EVENT_HEAD = re.compile(r"^Island event (\d+)\s*$")
EVENTS_LOG = re.compile(r"^Virtual Villagers (\d) Island Events Log (\d+)\.txt$", re.I)
CHANGE = re.compile(r"^  ([^:]+): (.*?) -> (.*)$")
PREFS = ("Likes", "Dislikes")


class LostTitlesError(Exception):
    """Nothing was changed (or everything was put back); the message says why."""


# ---------------------------------------------------------------------------
# Words
# ---------------------------------------------------------------------------

def _prefs(data, at: int, game: int) -> dict[str, list[int]]:
    """The villager's likes and dislikes arrays as the save holds them (whose name is at `at`)."""
    f = ln.FIELDS[game]
    return {label: list(struct.unpack_from(f"<{f.slots}i", data, at + off))
            for label, off in (("Likes", f.likes), ("Dislikes", f.dislikes))}


def list_text(game: int, values: list[int]) -> str:
    """Every filled slot's word, ", " between them, or "(none)" -- VillagePreferenceListText, which
    the Island Events log's "Likes: old -> new" lines print."""
    words = PREFERENCES[game]
    out = ""
    for v in values:
        if 0 <= v < len(words):
            # preference_list_text: a word fits when used + ", " + word + NUL <= the buffer.
            if len(out) + (2 if out else 0) + len(words[v]) + 1 > LIST_ROOM:
                break
            out += (", " if out else "") + words[v]
    return out or "(none)"


def _identity(name: bytes, game: int, prefs: dict[str, list[int]]) -> int:
    """vv_title_identity from the parts: the name, 0xFF, the likes and the dislikes arrays."""
    f = ln.FIELDS[game]
    h = ln._fnv(ln.FNV_BASIS, name.split(b"\0", 1)[0][:f.name_cap])
    h = ln._fnv(h, b"\xff")
    h = ln._fnv(h, struct.pack(f"<{f.slots}i", *prefs["Likes"]))
    h = ln._fnv(h, struct.pack(f"<{f.slots}i", *prefs["Dislikes"]))
    return h or 1


def undo(game: int, now: list[int], old_words: str, new_words: str) -> list[tuple[int, ...]] | None:
    """The arrays a "Likes: <old_words> -> <new_words>" change can have started from, given what the
    save holds now: those changing the fewest slots (an emptied slot taken as -1).  None when the
    change line does not fit what the save holds (changed again since) or cannot be read."""
    words = PREFERENCES[game]
    if list_text(game, now) != new_words or "(changed)" in (old_words, new_words):
        return None
    old = [] if old_words == "(none)" else old_words.split(", ")
    if any(w not in words for w in old):
        return None
    values = sorted({-1} | {i for i, w in enumerate(words) if w in old})
    for k in range(len(now) + 1):
        found = set()
        for slots in combinations(range(len(now)), k):
            for picked in product(values, repeat=k):
                cand = list(now)
                for s, v in zip(slots, picked):
                    cand[s] = v
                if any(cand[s] == now[s] for s in slots):
                    continue
                if list_text(game, cand) == old_words:
                    found.add(tuple(cand))
        if found:
            return sorted(found)
    return []


# ---------------------------------------------------------------------------
# The Island Events records
# ---------------------------------------------------------------------------

@dataclass
class Event:
    """One "Island event <n>" record of one villager."""
    block: object                   # vv_log_additions.Block
    order: tuple                    # (the log file's number, the record's line): oldest first
    name: str | None
    head: int | None
    body: int | None
    likes: str | None               # the record's own Likes / Dislikes lines (every word; one in older logs)
    dislikes: str | None
    custom: str | None              # its "Custom title:" line, when it has one
    event: str
    changes: dict = field(default_factory=dict)     # label -> (old, new)
    gone: bool = False

    @property
    def identity(self) -> tuple:
        return (self.name, self.head, self.body)

    @property
    def where(self) -> str:
        return f"{self.block.heading} ({self.event})"


def _int(text: str | None) -> int | None:
    try:
        return int(text) if text is not None else None
    except ValueError:
        return None


def parse(b, order: tuple) -> Event:
    lines = b.lines[1:]
    split = next((k for k, line in enumerate(lines) if line.startswith("  Dislikes:") and not CHANGE.match(line)),
                 None)
    head_lines = lines if split is None else lines[:split + 1]
    rest = [] if split is None else lines[split + 1:]

    def value(label: str) -> str | None:
        for line in head_lines:
            if line.startswith(f"  {label}:") and not CHANGE.match(line):
                return line.split(":", 1)[1].strip()
        return None
    changes = {}
    for line in (rest if split is not None else [x for x in lines if CHANGE.match(x)]):
        m = CHANGE.match(line.rstrip())
        if m and m.group(1) not in changes:
            changes[m.group(1)] = (m.group(2).strip(), m.group(3).strip())
    return Event(b, order, value("Name"), _int(value("Head")), _int(value("Body")), value("Likes"),
                 value("Dislikes"), value("Custom title"), value("Event") or "an island event", changes,
                 any(line.rstrip() == "  Gone: yes" for line in lines))


def events(folder: Path, game: int, slot: int) -> list[Event]:
    """Every villager's "Island event <n>" record under this slot's village, oldest first."""
    import vv_log_additions as additions
    checker = tools.load_checker()
    villages = additions.current_villages(folder, game, slot)
    out = []
    for path in checker.log_files(Path(folder)):
        m = EVENTS_LOG.match(path.name)
        if not m or int(m.group(1)) != game:
            continue
        for b in additions.blocks(path):
            if b.of(slot, game, villages) and EVENT_HEAD.match(b.heading):
                e = parse(b, (int(m.group(2)), b.start))
                if e.name:
                    out.append(e)
    return sorted(out, key=lambda e: e.order)


# ---------------------------------------------------------------------------
# The files
# ---------------------------------------------------------------------------

def _read_file(path: Path, magic: bytes, version: int, game: int, header: int, size: int,
               most: int) -> list[bytes] | None:
    """The entries of a valid file, [] when it is missing, None when it is there but not a file of
    this format for this game (it is then never rewritten)."""
    if not path.is_file():
        return []
    data = path.read_bytes()
    if len(data) < header or data[:4] != magic or struct.unpack_from("<II", data, 4) != (version, game):
        return None
    count = struct.unpack_from("<I", data, 12)[0]
    if count > most or len(data) != header + size * count:
        return None
    return [data[header + size * k:header + size * (k + 1)] for k in range(count)]


def title_valid(title: str) -> bool:
    """custom_titles.h vv_title_valid: 1..31 printable ASCII characters, not all spaces."""
    return 0 < len(title) < TITLE_BYTES and all(0x20 <= ord(c) <= 0x7E for c in title) and title.strip() != ""


def _read_titles(path: Path, game: int) -> list[vv_titles_file.Entry] | None:
    """The entries of the Custom Titles file (version 3, or 2), [] when it is missing, None when it is
    there but not a file this game reads (it is then never rewritten)."""
    if not path.is_file():
        return []
    got = vv_titles_file.read(path.read_bytes(), game)
    return None if got is None else got[1]


def _held_for(game: int, entries: list[vv_titles_file.Entry], identity: int, looks: dict,
              data: bytes | None = None, at: int | None = None) -> bool:
    """Whether the titles file holds a title (bound or pending) for the villager of this title identity
    and these looks: an entry of that identity that could be them (vv_titles_file.could_be, as the
    game's load matches it).  Two villagers of one identity with their own looks each hold their own.
    The head and body only break ties (the owner, v1.35.80 update: a change of looks never makes a
    villager someone else): an entry kept under other looks is theirs unless another villager of the
    identity in the save (`data`, theirs at `at`) has exactly the entry's looks."""
    could = [e for e in entries if e.identity == identity and vv_titles_file.could_be(game, e, looks)]
    if not could:
        return False
    if any(not e.known or (e.head, e.body) == (looks["head"], looks["body"]) for e in could):
        return True
    if data is None:
        return True
    f = ln.FIELDS[game]
    others = [vv_titles_file.looks_from_save(game, data, a) for a in ln._entries(game, data)
              if a != at and ln._title_identity(data, a, f) == identity]
    return any(not any((o["head"], o["body"]) == (e.head, e.body) for o in others) for e in could)

def _record_index(game: int, data: bytes, at: int) -> int:
    """The villager's record number: the games load a save packed into records 0, 1, 2 ... in the
    order it holds them (story_titles.inc titles_follow)."""
    checker = tools.load_checker()
    if game == 1:
        return (at - (checker.VV1_BLOCK0 - checker.VV1_BASE + 0x370)) // checker.VV1_STRIDE
    return checker.villager_offsets(game, data, []).index(at)


# ---------------------------------------------------------------------------
# Surveying
# ---------------------------------------------------------------------------

@dataclass
class Restore:
    """One title or former-Heathen mark to give back to one villager."""
    kind: str                       # "title" or "former"
    loss: str                       # what was lost: the candidates of one loss share it
    villager: ln.Living
    index: int                      # their record number now
    identity: int                   # their identity now
    record: str                     # "Island event 12 (Faces in the Night)"
    title: str = ""                 # "title": the title
    rekey: int | None = None        # "title": an orphaned entry at their record re-keyed (its identity);
                                    # "former": the entry's identity now (re-keyed to `identity`)
    former_kind: int | None = None
    question: str | None = None     # None: certain

    @property
    def key(self) -> str:
        return f"{self.kind}|{self.loss}|{self.villager.at}"

    def describe(self) -> str:
        v = self.villager
        who = f"{v.name} (head {v.head}, body {v.body})"
        if self.kind == "title":
            return f"{who}: Custom title \"{self.title}\" (lost in {self.record})"
        mark = FORMER_KINDS.get(self.former_kind, "former Heathen")
        return f"{who}: Former Heathen mark ({mark}), left behind after {self.record}"


@dataclass
class Survey:
    certain: list[Restore]
    questions: list[Restore]
    notes: list[str]

    @property
    def found(self) -> bool:
        return bool(self.certain or self.questions)


def _who(e: Event) -> str:
    return f"{e.name} (head {e.head}, body {e.body})"


def _words_now(game: int, prefs: dict, e: Event) -> bool:
    """Whether the villager's likes and dislikes now read as the record says the event left them."""
    for label, own in (("Likes", e.likes), ("Dislikes", e.dislikes)):
        if label in e.changes:
            if list_text(game, prefs[label]) != e.changes[label][1]:
                return False
        elif own is not None and not tools.preferences_agree(own, list_text(game, prefs[label])):
            return False
    return True


def survey(folder: Path, game: int, slot: int) -> Survey:
    """What can be given back, what must be asked, and what cannot be done.  Reads only."""
    import vv_log_additions as additions
    folder = Path(folder)
    if additions.current_villages(folder, game, slot) is None:
        return Survey([], [], ["The save's tribe name could not be read, so no lost title is looked for."])
    recs = events(folder, game, slot)
    out = Survey([], [], [])
    if not recs:
        return out
    data = ln.save_path(folder, game, slot).read_bytes()
    people = ln.living(folder, game, slot)
    f = ln.FIELDS[game]
    prefs = {v.at: _prefs(data, v.at, game) for v in people}
    ids = {v.at: ln._title_identity(data, v.at, f) for v in people}
    carriers: dict[int, int] = {}
    for v in people:
        carriers[ids[v.at]] = carriers.get(ids[v.at], 0) + 1
    try:
        page = additions.population_page(folder, slot, game)[1]
    except (OSError, ValueError):
        page = {}
    _survey_titles(folder, game, slot, data, recs, people, prefs, ids, carriers, page, out)
    if game == 5:
        _survey_former(folder, slot, data, recs, people, prefs, ids, carriers, out)
    return out


def _survey_titles(folder, game, slot, data, recs, people, prefs, ids, carriers, page, out: Survey) -> None:
    lost = [e for e in recs if "Custom title" in e.changes and e.changes["Custom title"][1].lower() == "none"
            and e.changes["Custom title"][0].lower() != "none" and any(p in e.changes for p in PREFS)
            and not e.gone and "Name" not in e.changes]
    if not lost:
        return
    path = layout.route(folder, TITLES_FILE.format(slot=slot))
    entries = _read_titles(path, game)
    if entries is None:
        out.notes.append(f"{path.name} is not a titles file this game reads, so no lost title is restored "
                         "into it (it is left as it is).")
        return
    # A pending title (kept for a villager who could not be told apart after a load) is held too: it
    # is never restored a second time, and the reconciliation asks about it.  Held FOR THIS VILLAGER
    # (v1.35.71 v2): an entry of their identity that could be them by the looks it keeps, as the game's
    # load matches it (vv_titles_file.could_be; an older file's entry keeps no looks: anyone of its
    # identity).  Another villager of the same identity with their own looks and title (a twin) does not
    # hold theirs -- that hid a lost title, or refused a restore every time.
    def held(v) -> bool:
        return _held_for(game, entries, ids[v.at], vv_titles_file.looks_from_save(game, data, v.at), data, v.at)

    at_index = {e.index: e for e in entries if not e.pending}
    for e in lost:
        title = e.changes["Custom title"][0]
        what = f"{_who(e)} lost the title \"{title}\" in {e.where}"
        if not title_valid(title):
            out.notes.append(f"{what}, but that is not a title the game can show; it is not restored.")
            continue
        exact = [v for v in people if v.identity == e.identity]
        same_name = [v for v in people if v.name == e.name and v.identity != e.identity]
        later = [x for x in recs if x.order > e.order
                 and (x.identity == e.identity or any(x.identity == v.identity for v in exact + same_name))]
        if any("Custom title" in x.changes or x.custom is not None for x in later):
            out.notes.append(f"{what}; a later Island Events record shows their title changed again, so it is "
                             "left as it is.")
            continue
        if any(x.gone or "Name" in x.changes for x in later):
            out.notes.append(f"{what}; a later Island Events record shows them gone or renamed, so it is not "
                             "restored.")
            continue
        candidates = exact or [v for v in same_name if _words_now(game, prefs[v.at], e)]
        if not candidates:
            out.notes.append(f"{what}; no living villager is them now, so it is not restored.")
            continue
        found = []
        for v in candidates:
            if held(v):
                out.notes.append(f"{what}; the titles file already holds a title for {v.name} (head {v.head}, "
                                 f"body {v.body}) -- shown, or pending until they can be told apart -- which is kept.")
                continue
            # Every block of their name and looks on the page (two villagers may share them; Page.blocks):
            # one showing another title may be theirs, so it is left as it is -- never a guess.
            shown = getattr(page, "blocks", {}).get(v.identity) or ([page[v.identity]] if v.identity in page else [])
            other = next((t for t in (b.value("Custom title") for b in shown)
                          if t is not None and t.strip().lower() not in ("", "none", "-", title.lower())), None)
            if other is not None:
                out.notes.append(f"{what}; the latest Village Population page shows {v.name} as \"{other}\", "
                                 "so it is left as it is.")
                continue
            index = _record_index(game, data, v.at)
            rekey = None
            there = at_index.get(index)
            if there is not None:
                there_id = there.identity
                there_title = there.title
                if there_title == title and there_id not in carriers:
                    rekey = there_id        # their own title, left behind under the old identity
                else:
                    out.notes.append(f"{what}; another title (\"{there_title}\") is kept at {v.name}'s record "
                                     f"number ({index}), so it is not restored.")
                    continue
            if rekey is None and len(entries) >= TITLES_MAX:
                out.notes.append(f"{what}; the titles file is full, so it is not restored.")
                continue
            found.append(Restore("title", f"{e.block.path.name}:{e.block.start}", v, index, ids[v.at], e.where,
                                 title=title, rekey=rekey))
        if not found:
            continue
        sure = (len(exact) == 1 and len(found) == 1 and found[0].villager is exact[0]
                and _words_now(game, prefs[exact[0].at], e))
        if sure:
            out.certain.append(found[0])
            continue
        for r in found:
            v = r.villager
            why = []
            if len(candidates) > 1:
                why.append(f"{len(candidates)} living villagers could be them")
            if v.identity != e.identity:
                why.append(f"the record names head {e.head}, body {e.body}")
            if not _words_now(game, prefs[v.at], e):
                why.append("their likes or dislikes changed again since")
            likes = list_text(game, prefs[v.at]["Likes"])
            dislikes = list_text(game, prefs[v.at]["Dislikes"])
            r.question = (f"Was {v.name} (head {v.head}, body {v.body}; likes {likes}; dislikes {dislikes}) the "
                          f"villager the Island Events log says lost the title \"{title}\" in {e.where}? "
                          f"Restore it?" + (f" ({'; '.join(why)}.)" if why else ""))
            out.questions.append(r)


def _survey_former(folder, slot, data, recs, people, prefs, ids, carriers, out: Survey) -> None:
    game = 5
    path = layout.route(folder, FORMER_FILE.format(slot=slot))
    entries = _read_file(path, FORMER_MAGIC, FORMER_VERSION, game, FORMER_HEADER, FORMER_ENTRY, 1024)
    if not entries:
        if entries is None:
            out.notes.append(f"{path.name} is not a Former Heathens file this game reads; it is left as it is.")
        return
    by_id: dict[int, list[int]] = {}
    for e in entries:
        identity, kind = struct.unpack("<II", e)
        by_id.setdefault(identity, []).append(kind)
    f = ln.FIELDS[game]
    for v in people:
        if ids[v.at] in by_id:
            continue                        # their mark is under who they are now
        changed = [e for e in recs if e.identity == v.identity and any(p in e.changes for p in PREFS)
                   and not e.gone and "Name" not in e.changes]
        if not changed:
            continue
        name = bytes(data[v.at:v.at + f.name_cap])
        look_alikes = sum(1 for w in people if w.identity == v.identity) > 1
        states = [{p: tuple(prefs[v.at][p]) for p in PREFS}]
        for e in reversed(changed):
            nxt = []
            for state in states:
                options = {}
                for label in PREFS:
                    if label in e.changes:
                        undone = undo(game, list(state[label]), *e.changes[label])
                        options[label] = undone
                    else:
                        options[label] = [state[label]]
                if any(o is None for o in options.values()):
                    continue
                nxt += [{"Likes": a, "Dislikes": b} for a in options["Likes"] for b in options["Dislikes"]]
            if not nxt:
                out.notes.append(f"{v.name} (head {v.head}, body {v.body}): their likes or dislikes before "
                                 f"{e.where} could not be rebuilt from the records, so a former-Heathen mark "
                                 "left under them cannot be found.")
                break
            states = nxt
            olds = {}
            for state in states:
                olds[_identity(name, game, {p: list(state[p]) for p in PREFS})] = state
            hits = [i for i in olds if i in by_id]
            if not hits:
                continue
            r_list = []
            for old in hits:
                kinds = by_id[old]
                if len(kinds) != 1 or old in carriers:
                    out.notes.append(f"{v.name} (head {v.head}, body {v.body}): the former-Heathen entry they "
                                     f"had before {e.where} is shared, so whose it is cannot be told; it is "
                                     "left as it is.")
                    continue
                r_list.append(Restore("former", f"entry {old:08X}", v, _record_index(game, data, v.at), ids[v.at],
                                      e.where, rekey=old, former_kind=kinds[0]))
            if len(states) == 1 and len(r_list) == 1 and not look_alikes:
                out.certain += r_list
            else:
                for r in r_list:
                    r.question = (f"{v.name} (head {v.head}, body {v.body}) had their likes or dislikes changed in "
                                  f"{e.where}. A former-Heathen mark ({FORMER_KINDS.get(r.former_kind, 'unknown')}) "
                                  "is kept under likes and dislikes they may have had before"
                                  + (" (another living villager looks the same)" if look_alikes else
                                     " (what they had before is not certain)")
                                  + ". Was it theirs? Give it back to them?")
                    out.questions.append(r)
            break
    # One entry two villagers could have had is nobody's for certain: each is asked.
    claims: dict[str, int] = {}
    for r in out.certain + out.questions:
        if r.kind == "former":
            claims[r.loss] = claims.get(r.loss, 0) + 1
    for r in [r for r in out.certain if r.kind == "former" and claims[r.loss] > 1]:
        out.certain.remove(r)
        r.question = (f"{r.villager.name} (head {r.villager.head}, body {r.villager.body}) is one of "
                      f"{claims[r.loss]} villagers a former-Heathen mark ({FORMER_KINDS.get(r.former_kind, 'unknown')}) "
                      f"left behind after {r.record} could be for. Was it theirs? Give it back to them?")
        out.questions.append(r)


# ---------------------------------------------------------------------------
# Restoring
# ---------------------------------------------------------------------------

@dataclass
class Result:
    restored: list[Restore]
    files: list[Path]
    backup: object


@dataclass
class _Change:
    path: Path
    original: bytes | None          # None: a file made new
    updated: bytes


def _plan(folder: Path, game: int, slot: int, chosen: list[Restore]) -> list[_Change]:
    changes = []
    titles = [r for r in chosen if r.kind == "title"]
    if titles:
        path = layout.route(folder, TITLES_FILE.format(slot=slot))
        original = path.read_bytes() if path.is_file() else None
        entries = _read_titles(path, game)
        if entries is None:
            raise LostTitlesError(f"{path.name} is not a titles file this game reads; nothing was changed.")
        data = ln.save_path(folder, game, slot).read_bytes()
        for r in titles:
            if not title_valid(r.title):
                raise LostTitlesError(f"\"{r.title}\" is not a title the game can show; nothing was changed.")
            looks = vv_titles_file.looks_from_save(game, data, r.villager.at)
            if _held_for(game, entries, r.identity, looks, data, r.villager.at):
                raise LostTitlesError(f"{r.villager.name} already has a title in {path.name}; nothing was changed.")
            same = [e for e in entries if not e.pending and e.index == r.index]
            if r.rekey is not None:
                if len(same) != 1 or same[0].identity != r.rekey:
                    raise LostTitlesError(f"{path.name} changed since it was read; nothing was changed.")
                same[0].identity = r.identity
                same[0].known = True
                for key, value in looks.items():
                    setattr(same[0], key, value)
            else:
                if same:
                    raise LostTitlesError(f"Record {r.index} already has a title in {path.name}; nothing was changed.")
                if len(entries) >= TITLES_MAX:
                    raise LostTitlesError(f"{path.name} is full; nothing was changed.")
                entries.append(vv_titles_file.Entry(r.index, r.identity, r.title, True, **looks))
        # Written in the file's own version, every other entry byte for byte (a new file: version 3).
        version = vv_titles_file.read(original, game)[0] if original is not None else vv_titles_file.VERSION
        changes.append(_Change(path, original, vv_titles_file.serialise(game, entries, version)))
    formers = [r for r in chosen if r.kind == "former"]
    if formers:
        path = layout.route(folder, FORMER_FILE.format(slot=slot))
        original = path.read_bytes()
        entries = _read_file(path, FORMER_MAGIC, FORMER_VERSION, game, FORMER_HEADER, FORMER_ENTRY, 1024)
        if not entries:
            raise LostTitlesError(f"{path.name} could not be read; nothing was changed.")
        entries = [bytearray(e) for e in entries]
        for r in formers:
            if any(struct.unpack_from("<I", e, 0)[0] == r.identity for e in entries):
                raise LostTitlesError(f"{r.villager.name} already has a former-Heathen mark; nothing was changed.")
            same = [e for e in entries if struct.unpack_from("<I", e, 0)[0] == r.rekey]
            if len(same) != 1:
                raise LostTitlesError(f"{path.name} changed since it was read; nothing was changed.")
            struct.pack_into("<I", same[0], 0, r.identity)
        changes.append(_Change(path, original, original[:FORMER_HEADER] + b"".join(bytes(e) for e in entries)))
    return changes


def _copy_before(folder: Path, change: _Change) -> str:
    """The file as it was, in Data\\Copies Made Before Repairs (never replacing a copy)."""
    if change.original is None:
        return "(a new file)"
    for k in range(1, 1000):
        target = tools.copy_before_repair(folder, change.path, COPY_SUFFIX + ("" if k == 1 else f"-{k}"))
        if not target.exists():
            break
    else:
        raise LostTitlesError(f"{change.path.name} has too many copies already; nothing was changed.")
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "xb") as copy:
        copy.write(change.original)
    return target.name


def restore(folder: Path, game: int, slot: int, chosen: set[str] | None = None,
            processes: vv_save_backup.ProcessController | None = None, now: datetime | None = None) -> Result:
    """Give back every certain title and mark (`chosen` None), or those whose Restore.key is in
    `chosen` (certain ones and the questions the player answered yes).  The survey is made again
    here, so nothing is written from a stale one; one villager per loss at most.  Refused while the
    game runs; the save folder is backed up first; any failure puts every file back."""
    folder = Path(folder)
    controller = processes if processes is not None else vv_save_backup.WindowsProcesses()
    tools._refuse_if_running(folder, controller)
    try:
        work = survey(folder, game, slot)
    except (struct.error, ValueError, OSError, ln.LastNamesError) as exc:
        raise LostTitlesError(f"A file could not be read ({exc}); nothing was changed.") from exc
    picked: list[Restore] = []
    losses = set()
    for r in work.certain + work.questions:
        if (chosen is None and r.question is None) or (chosen is not None and r.key in chosen):
            if r.loss in losses or any(p.villager.at == r.villager.at and p.kind == r.kind for p in picked):
                continue
            losses.add(r.loss)
            picked.append(r)
    if not picked:
        raise LostTitlesError(" ".join(work.notes) or "No lost title or former-Heathen mark was found to restore.")
    changes = _plan(folder, game, slot, picked)
    try:
        backup = vv_save_backup.copy_save_folder(folder, now or datetime.now(), suffix=BACKUP_LABEL)
    except vv_save_backup.BackupError as exc:
        raise LostTitlesError(f"The backup failed, so nothing was changed. {exc}") from exc
    tools._refuse_if_running(folder, controller)
    copies = [_copy_before(folder, c) for c in changes]
    done: list[_Change] = []
    try:
        for change in changes:
            current = change.path.read_bytes() if change.path.is_file() else None
            if current != change.original:
                raise LostTitlesError(f"{change.path.name} changed while the titles were being restored.")
            done.append(change)
            change.path.parent.mkdir(parents=True, exist_ok=True)
            ln._write(change.path, change.updated)
    except (OSError, LostTitlesError, ln.LastNamesError) as exc:
        problems = []
        for change in reversed(done):
            try:
                if change.original is not None:
                    if change.path.read_bytes() != change.original:
                        ln._write(change.path, change.original)
                elif change.path.exists():
                    change.path.unlink()
            except (OSError, ln.LastNamesError) as undo_exc:
                problems.append(f"{change.path.name}: {undo_exc}")
        if problems:
            raise LostTitlesError(f"Restoring the titles failed ({exc}) and these files could not be put back: "
                                  f"{'; '.join(problems)}. Your backup is in {backup.backup_folder}.") from exc
        raise LostTitlesError(f"Restoring the titles failed ({exc}); every file was put back as it was. "
                              f"A backup is in {backup.backup_folder}.") from exc
    village = next((e.block.village for e in events(folder, game, slot) if e.block.village), None)
    try:
        note_restore(folder, game, village, picked, [(c.path, name) for c, name in zip(changes, copies)],
                     backup, now, slot)
    except OSError:
        pass                                # the restore stands; Check Saves & Logs still sees it
    return Result(picked, [c.path for c in changes], backup)


def note_restore(folder: Path, game: int, village: str | None, restored: list[Restore], files: list[tuple],
                 backup, now: datetime | None = None, slot: int | None = None) -> None:
    """One "Repair <n>" record in the Repairs Made log (native/shared/repairs_log.h's shape, numbered as
    src/vv_log_tools.py note_word_repair numbers it)."""
    if not restored:
        return
    header = village or "Village: (all villages in this save folder)"
    path, text = tools.repair_record_start(folder, game, header, layout.header_slot(village) or slot, now)
    text += ("  Checked: custom titles and former-Heathen marks a change of likes or dislikes took away, "
             "against the Island Events log\r\n")
    for r in restored:
        text += f"  Restored: {r.describe()}\r\n"
    for p, copy in files:
        text += f"  File: {Path(p).relative_to(folder)} -- copy kept: {copy}\r\n"
    text += f"  Backup: {Path(backup.backup_folder).name}\r\n\r\n"
    with open(path, "ab") as log:
        log.write(text.encode("latin-1", "replace"))
