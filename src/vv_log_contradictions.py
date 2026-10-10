"""Records in the logs that contradict each other, found by Check Saves & Logs and put right by
Repair Saves & Logs (all five games).

The owner (2026-10-10), on the A New Home Births and Conceptions log: Cheop Bahati had a Birth record
and, further down, a backfilled "Arrived 11 ... How: unknown / Note: Recorded afterwards (arrived
before this log existed)"; Lulu Chuchip, the Golden Child, the same; Hoani Chuchip two Arrived
records -- "make sure no bugs like this or similar logging bugs are in any of the 5 games".  The
arrival backfill had matched the log by name, head and body, and these records carried a name (or a
look) of their day: "Cheop" and "Hoani" before last names were given
(native/parentage_export/arrival_backfill.inc now follows them).  The records already written stay
contradictory until repaired, so:

  BORN AND ARRIVED, OR ARRIVED TWICE.  One villager (the same name, head and body, a look followed
  through every "Appearance changed" record) with more Birth and Arrived records than villagers who
  could own them -- the living villagers of the save with that name and look, and the dead ones
  the Deaths logs list (never fewer than one).  A Birth record is never taken out; the surplus is
  taken from the Arrived records the backfill wrote ("Note: Recorded afterwards (arrived before
  this log existed)"), "How: unknown" first, then the latest.  Check: WRONG.  Repair: asks
  (taken out, by default), the record kept in the copy of the log made before the repair.

  A DEATH NUMBER TWICE.  "Death n" repeated across the game's Deaths logs, under both folder names
  (an older build numbered a new folder's records from its own records alone -- the owner's A New
  Home log has "Death 15" four times).  A record kept word for word in both folders is one record.
  Check: WRONG.  Repair: each later repeat takes the next number after the highest.

  A REPAIR NUMBER TWICE.  A Repairs log file of the same number in both "Repairs" and "Repairs
  Made" whose "Repair n" numbers collide (the owner's: Repair 1-11, then Repair 1 again).  Check:
  WRONG.  Repair: the newer folder's records are numbered on after the older folder's.

  REPORTED ONLY (NOTE): a Death and a Disappeared record of one villager; an Unaccounted "Left the
  village" record of one with a Death record; a Death record of a villager the save has alive at
  that age or older (New Believers' Reanimate and a revived skeleton bring the dead back, so none
  of these is proof by itself).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import vv_log_tools as tools
import vv_save_layout as layout

BACKFILL_NOTE = "Recorded afterwards (arrived before this log existed)"
TAKE_OUT = "Take out the backfilled record (the villager's other record stays)"
KEEP = "Keep both (they are two different villagers)"
RENUMBER = "Give it the next free number"
LEAVE = "Don't know / leave it (changes nothing)"
RETRO_YES = "Yes: correct the older records to match"
RETRO_NO = "No: leave every past record as it is (not asked again)"
# The contradictions the player chose to leave in the past records (Retroactively edit records? No):
# remembered per slot, so they are not asked about again until something new contradicts.
KEPT = layout.DATA + r"\Log Checks\Virtual Villagers {game} Contradictions Left - Save {slot}.txt"


@dataclass
class Found:
    kind: str                          # "born_and_arrived" | "death_number" | "repair_number" | "note"
    text: str                          # Check Saves & Logs' words
    edits: list = field(default_factory=list)   # vv_log_additions.Edit
    question: object | None = None     # vv_log_additions.Question, for a record taken out
    ident: str = ""                    # the same contradiction, told apart from every other one

    @property
    def wrong(self) -> bool:
        return self.kind != "note"


def _births_paths(folder: Path, game: int) -> list[Path]:
    checker = tools.load_checker()
    return [path for root in (checker.LOGS, "VVFP Logs")
            for sub, words in (("Births and Conceptions", "Births and Conceptions Log"),
                               ("Tribe Parental Records", "Parentage Log"))
            for path in checker.numbered(folder / root / sub, f"Virtual Villagers {game} {words}")]


def _int(v: str | None) -> int | None:
    try:
        return int(v) if v is not None else None
    except ValueError:
        return None


def _child(b) -> tuple | None:
    """(name, head, body) of a Birth record's child."""
    name = b.value("Child")
    head = body = None
    for line in b.lines:
        m = re.match(r"^    (Head|Body): (-?\d+)\s*$", line)
        if m and m.group(1) == "Head" and head is None:
            head = int(m.group(2))
        elif m and m.group(1) == "Body" and body is None:
            body = int(m.group(2))
        if line.startswith("  Mother:") or line.startswith("  Father:"):
            break
    return (name, head, body) if name else None


def _end_with_blank(lines: list[str], b) -> int:
    """The last index of block `b`, with the blank line after it (so taking it out leaves one)."""
    end = b.start + len(b.lines) - 1
    return end + 1 if end + 1 < len(lines) and not lines[end + 1].strip() else end


def _born_and_arrived(folder: Path, game: int, slot: int) -> list[Found]:
    import vv_log_additions as additions
    villages = additions.current_villages(folder, game, slot)
    records = []                               # (block, kind, key)
    looks: dict[tuple, tuple] = {}
    texts: dict[Path, list[str]] = {}
    for path in _births_paths(folder, game):
        texts[path] = additions.read_lines(path)
        for b in additions.blocks(path, texts[path]):
            if not b.of(slot, game, villages):
                continue
            if b.heading == "Birth":
                key = _child(b)
                if key:
                    records.append((b, "birth", key))
            elif re.fullmatch(r"Arrived \d+", b.heading):
                key = b.identity
                if key[0]:
                    records.append((b, "arrived", key))
            elif b.heading == "Appearance changed":
                name = b.value("Name")
                old = (name, _int(b.value("Old head")), _int(b.value("Old body")))
                new = (name, _int(b.value("New head")), _int(b.value("New body")))
                if name and None not in old and None not in new and old != new:
                    looks.setdefault(old, new)

    def now(key: tuple) -> tuple:
        seen = set()
        while key in looks and key not in seen:
            seen.add(key)
            key = looks[key]
        return key
    import vv_last_names as ln
    try:
        alive = [v.identity for v in ln.living(folder, game, slot)]
    except (ln.LastNamesError, OSError, ValueError, IndexError):
        alive = None
    dead = [b.identity for b in additions.person_blocks(folder, slot, game)
            if b.heading.startswith("Death") or b.heading.startswith("Disappeared")]
    by_key: dict[tuple, list] = {}
    for b, kind, key in records:
        by_key.setdefault(now(key), []).append((b, kind))
    out = []
    for key, recs in by_key.items():
        if len(recs) < 2:
            continue
        owners = (sum(1 for k in alive if now(k) == key) if alive is not None else 1) \
            + sum(1 for k in dead if now(k) == key)
        surplus = len(recs) - max(1, owners)
        if surplus <= 0:
            continue
        backfilled = [(b, kind) for b, kind in recs if kind == "arrived" and BACKFILL_NOTE in (b.value("Note") or "")]
        # "How: unknown" first, then the latest.
        backfilled.sort(key=lambda r: ((r[0].value("How") or "") != "unknown", -r[0].start, str(r[0].path)))
        if len(backfilled) == len(recs):           # every record a backfill: one is kept
            backfilled = backfilled[:-1]
        others = [b for b, _ in recs]
        for b, _kind in backfilled[:surplus]:
            if (b.value("How") or "").strip().lower() == "unknown" and any(
                    kind == "birth" and _child(o) == b.identity for o, kind in recs):
                continue        # vv_log_additions.plan_born_arrived and the checker take this one
            kept = [o for o in others if o is not b]
            what = ", ".join(f"{o.heading} ({o.path.name})" for o in kept)
            ident = f"born_and_arrived|{b.heading}|{key[0]}|{key[1]}|{key[2]}"
            key_q = f"contradiction|{ident}"
            question = additions.Question(
                key_q, f"{key[0]} (head {key[1]}, body {key[2]}) has {len(recs)} Birth / Arrived records "
                       f"({what}, and {b.heading}) but {max(1, owners)} villager(s) to own them. "
                       f"{b.heading} was backfilled later. Take it out?",
                [TAKE_OUT, KEEP, additions.DONT_KNOW], TAKE_OUT)
            edit = ("remove", b.path, b.start, _end_with_blank(texts[b.path], b) - b.start + 1)
            out.append(Found("born_and_arrived",
                             f"{key[0]} (head {key[1]}, body {key[2]}) has both {what} and a backfilled "
                             f"{b.heading} in {b.path.name} (line {b.start + 1}): one villager recorded twice "
                             "(repairable: Repair Saves & Logs takes the backfilled record out)",
                             [edit], question, ident))
    return out


def _death_numbers(folder: Path, game: int, slot: int) -> list[Found]:
    import vv_log_additions as additions
    checker = tools.load_checker()
    villages = additions.current_villages(folder, game, slot)
    seen_text: dict[str, int] = {}
    numbered: list[tuple[int, object, str]] = []
    for name in checker.DEATHS_FOLDERS(folder):
        for path in checker.numbered(folder / checker.LOGS / name, f"Virtual Villagers {game} Deaths Log"):
            for b in additions.blocks(path):
                m = re.fullmatch(r"Death (\d+)", b.heading)
                if not m or not b.of(slot, game, villages):
                    continue
                body = "\n".join(b.lines[1:])
                if name == layout.DEATHS_LOGS and seen_text.get(body):
                    seen_text[body] -= 1               # the same record kept in both folders: one
                    continue
                if name != layout.DEATHS_LOGS:
                    seen_text[body] = seen_text.get(body, 0) + 1
                numbered.append((int(m.group(1)), b, body))
    if not numbered:
        return []
    highest = max(n for n, _b, _t in numbered)
    used: set[int] = set()
    out = []
    for n, b, _body in numbered:
        if n not in used:
            used.add(n)
            continue
        highest += 1
        out.append(Found("death_number",
                         f"\"Death {n}\" is used again for {b.value('Name') or 'a villager'} in "
                         f"{b.path.parent.name}\\{b.path.name} (line {b.start + 1}) (repairable: Repair Saves & Logs "
                         f"numbers it Death {highest})",
                         [("replace", b.path, b.start, f"Death {highest}")],
                         ident=f"death_number|{n}|{b.value('Name')}|{b.value('Age at death')}"))
    return out


def _repair_numbers(folder: Path, game: int) -> list[Found]:
    import vv_log_additions as additions
    checker = tools.load_checker()
    old_dir = folder / checker.LOGS / "Repairs"
    new_dir = folder / checker.LOGS / layout.REPAIRS_LOGS
    out = []
    for new in checker.numbered(new_dir, f"Virtual Villagers {game} Repairs Log"):
        old = old_dir / new.name
        if not old.is_file():
            continue
        before = sum(1 for line in additions.read_lines(old) if re.match(r"^Repair \d+\s*$", line))
        lines = additions.read_lines(new)
        k = 0
        for i, line in enumerate(lines):
            m = re.match(r"^Repair (\d+)\s*$", line)
            if not m:
                continue
            k += 1
            want = before + k
            if int(m.group(1)) <= before:
                out.append(Found("repair_number",
                                 f"\"Repair {m.group(1)}\" in {layout.REPAIRS_LOGS}\\{new.name} repeats a number of "
                                 f"Repairs\\{old.name} (repairable: Repair Saves & Logs numbers it Repair {want})",
                                 [("replace", new, i, f"Repair {want}")],
                                 ident=f"repair_number|{new.name}|{i}"))
    return out


def _notes(folder: Path, game: int, slot: int) -> list[Found]:
    import vv_log_additions as additions
    out = []
    people = additions.person_blocks(folder, slot, game)
    deaths: dict[tuple, list] = {}
    for b in people:
        if re.fullmatch(r"Death \d+", b.heading):
            deaths.setdefault(b.identity, []).append(b)
    for b in people:
        if b.heading.startswith("Disappeared") and b.identity in deaths:
            out.append(Found("note", f"{b.identity[0]} has both a Death and a Disappeared record"))
        if b.heading.startswith("Unaccounted") and (b.value("What") or "").startswith("Left") \
                and b.identity in deaths:
            out.append(Found("note", f"{b.identity[0]} is Unaccounted (left the village) and has a Death record"))
    import vv_last_names as ln
    try:
        alive = ln.living(folder, game, slot)
    except (ln.LastNamesError, OSError, ValueError, IndexError):
        alive = []
    checker = tools.load_checker()
    try:
        data = (Path(folder) / f"{checker.SAVE_STEMS[game]}{slot}.ldw").read_bytes()
        ages = {}
        roster = checker.vv1_roster(data) if game == 1 else checker.vv25_roster(game, data, [])
        for v in roster:
            ages.setdefault((v.name, v.head, v.body), []).append(v.age)
    except (OSError, ValueError, KeyError):
        ages = {}
    for v in alive:
        for d in deaths.get(v.identity, []):
            age = d.int_value("Age at death")
            if age is not None and any(a >= age for a in ages.get(v.identity, [])):
                out.append(Found("note", f"{v.name} has a Death record (age {age}) and is alive in the save at that "
                                         "age or older (brought back, or a namesake with the same looks)"))
                break
    return out


def left_alone(folder: Path, game: int, slot: int) -> set[str]:
    """The contradictions the player chose to leave in the past records (KEPT)."""
    path = layout.find(Path(folder), KEPT.format(game=game, slot=slot))
    try:
        return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}
    except OSError:
        return set()


def find(folder: Path, game: int, slot: int) -> list[Found]:
    """Every contradiction above in this slot's village's logs.  Reads only.  One the player chose
    to leave in the past records ("Retroactively edit records?" No) is a note, never asked again."""
    folder = Path(folder)
    found = (_born_and_arrived(folder, game, slot) + _death_numbers(folder, game, slot)
             + _repair_numbers(folder, game) + _notes(folder, game, slot))
    kept = left_alone(folder, game, slot)
    for f in found:
        if f.wrong and f.ident in kept:
            f.kind = "note"
            f.text += " -- left in the past records, as you chose"
            f.text = f.text.replace(" (repairable: ", " (was repairable: ")
    return found


def retro_key(found: Found) -> str:
    return f"retro|{found.ident}"


def plan(folder: Path, game: int, slot: int):
    """Repair Saves & Logs' kind (the owner, 2026-10-10: "ASK THE PLAYER WITH A PROMPT IF YOU SEE ANY
    CONTRADICTIONS IN THE RECORDS", and "Retroactively edit records? yes/no"): for each contradiction
    two questions -- what to do (the sensible resolution, or "Don't know / leave it", which changes
    nothing), and whether to correct the older records.  A record is taken out or renumbered only
    when the player chose the resolution AND answered Yes; No leaves every past record as it is and
    is remembered (remember), so it is not asked again."""
    import vv_log_additions as additions
    kind = additions.Kind("contradictions", "Records that contradict each other")
    for found in find(folder, game, slot):
        if not found.wrong:
            kind.notes.append(found.text)
            continue
        question = found.question
        if question is None:                       # a number used twice
            question = additions.Question(
                f"contradiction|{found.ident}", f"{found.text.split(' (repairable')[0]}. What should be done?",
                [RENUMBER, LEAVE], RENUMBER)
        else:
            question.options = [o for o in question.options if o != additions.DONT_KNOW] + [LEAVE]
        resolution = question.options[0]
        retro = additions.Question(
            retro_key(found), f"{found.text.split(' (repairable')[0]}: retroactively edit records?",
            [RETRO_YES, RETRO_NO], RETRO_YES)
        kind.questions[question.key] = question
        kind.questions[retro.key] = retro
        for edit in found.edits:
            if edit[0] == "remove":
                kind.removes.append(additions.Remove(edit[1], edit[2], edit[3], question.key, resolution,
                                                     also=[(retro.key, RETRO_YES)]))
            else:
                kind.replaces.append((edit[1], edit[2], edit[3], [(question.key, resolution),
                                                                  (retro.key, RETRO_YES)]))
    return kind


def remember(folder: Path, game: int, slot: int, kinds: list, answers: dict[str, str]) -> list[str]:
    """Every contradiction the player answered "Retroactively edit records?" No to, added to KEPT
    (appended; the file is the patcher's own, kept beside the Log Checks markers).  Returns them."""
    idents = []
    for kind in kinds:
        if kind.id != "contradictions":
            continue
        for key, _question in kind.questions.items():
            if key.startswith("retro|") and answers.get(key) == RETRO_NO:
                idents.append(key[len("retro|"):])
            elif key.startswith("contradiction|") and answers.get(key) == KEEP:   # not a contradiction
                idents.append(key[len("contradiction|"):])
    if not idents:
        return []
    path = layout.writable(Path(folder), KEPT.format(game=game, slot=slot))
    known = left_alone(folder, game, slot)
    new = [i for i in idents if i not in known]
    if new:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as kept:
            kept.write("".join(i + "\n" for i in new))
    return new
