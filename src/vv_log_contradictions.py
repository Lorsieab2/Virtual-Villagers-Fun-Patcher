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
# The contradictions the player chose to leave in the past records (Retroactively edit records? No)
# are remembered per slot, so they are not asked about again until something new contradicts: in the
# same decisions file as every other "No" (src/vv_log_decisions.py, which still reads the earlier
# "Contradictions Left" text file).


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
    return tools.load_checker().births_layout_files(folder, game)


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
            if additions.is_birth(b.heading):
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
    # The backfilled records plan_born_arrived offers (a duplicate of a real Arrived record of the same
    # name, head and body, when who is alive can be read): asked about there, never twice.
    offered_elsewhere = {(r.path, r.start) for r in additions.plan_born_arrived(folder, game, slot).removes}
    # ...and one it already asked about, answered "remove" with "Retroactively edit records?" No: the
    # player's answer is remembered (src/vv_log_decisions.py) and is never asked again here either.
    import vv_log_decisions
    settled = vv_log_decisions.decided(folder, game, slot, "born_arrived", "remove", villages)
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
            if (b.path, b.start) in offered_elsewhere:
                continue        # ...and so it does a backfill of a real Arrived record it offers itself
            kept = [o for o in others if o is not b]
            what = ", ".join(f"{o.heading} ({o.path.name})" for o in kept)
            if b.identity in settled:
                out.append(Found("note", f"{key[0]} (head {key[1]}, body {key[2]}) has both {what} and a backfilled "
                                         f"{b.heading} in {b.path.name} -- left in the past records, as you chose"))
                continue
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
    seen_text: dict[tuple, int] = {}
    numbered: list[tuple[int, object, str]] = []
    # "Death <n>" is numbered per GAME (src/vv_save_layout.py): every folder of the game is one
    # sequence -- an older build's "Deaths", the shared "Deaths and Disappearances" and every save
    # slot's own -- so a number is used twice wherever its two records are.
    old_dir = folder / checker.LOGS / "Deaths"
    for path in checker.game_logs(folder, layout.DEATHS_LOGS, f"Virtual Villagers {game} Deaths Log"):
        older = path.parent == old_dir
        for b in additions.blocks(path):
            m = re.fullmatch(r"Death (\d+)", b.heading)
            if not m or (b.game is not None and b.game != game):
                continue
            body = (b.village, "\n".join(b.lines[1:]))
            if not older and seen_text.get(body):
                seen_text[body] -= 1               # the same record kept in both folders: one
                continue
            if older:
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
        if not b.of(slot, game, villages):
            continue        # another village's record: put right when its own slot is checked
        highest += 1
        out.append(Found("death_number",
                         f"\"Death {n}\" is used again for {b.value('Name') or 'a villager'} in "
                         f"{_where(b.path)} (line {b.start + 1}) (repairable: Repair Saves & Logs "
                         f"numbers it Death {highest})",
                         [("replace", b.path, b.start, f"Death {highest}")],
                         ident=f"death_number|{n}|{b.value('Name')}|{b.value('Age at death')}"))
    return out


def _repair_numbers(folder: Path, game: int) -> list[Found]:
    import vv_log_additions as additions
    checker = tools.load_checker()
    old_dir = folder / checker.LOGS / "Repairs"
    new_dir = folder / checker.LOGS / layout.REPAIRS_LOGS
    stem = f"Virtual Villagers {game} Repairs Log"
    out = []
    # Every "Repair <n>" of the game as it will read once the shared folders' collisions below are put
    # right: what a save slot's own record is checked against (numbered per GAME, repairs_log.h).
    numbers: list[tuple[int, Path, int]] = []         # (number, file, line index), in reading order
    for path in checker.game_logs(folder, layout.REPAIRS_LOGS, stem):
        if layout.is_slot_folder(path):
            continue
        old = old_dir / path.name
        before = 0
        if path.parent == new_dir and old.is_file():
            before = sum(1 for line in additions.read_lines(old) if re.match(r"^Repair \d+\s*$", line))
        lines = additions.read_lines(path)
        k = 0
        for i, line in enumerate(lines):
            m = re.match(r"^Repair (\d+)\s*$", line)
            if not m:
                continue
            k += 1
            want = before + k
            if before and int(m.group(1)) <= before:
                out.append(Found("repair_number",
                                 f"\"Repair {m.group(1)}\" in {layout.REPAIRS_LOGS}\\{path.name} repeats a number of "
                                 f"Repairs\\{old.name} (repairable: Repair Saves & Logs numbers it Repair {want})",
                                 [("replace", path, i, f"Repair {want}")],
                                 ident=f"repair_number|{path.name}|{i}"))
                numbers.append((want, path, i))
            else:
                numbers.append((int(m.group(1)), path, i))
    slots = [path for path in checker.game_logs(folder, layout.REPAIRS_LOGS, stem) if layout.is_slot_folder(path)]
    for path in slots:
        for i, line in enumerate(additions.read_lines(path)):
            m = re.match(r"^Repair (\d+)\s*$", line)
            if m:
                numbers.append((int(m.group(1)), path, i))
    highest = max((n for n, _p, _i in numbers), default=0)
    used: set[int] = set()
    for n, path, i in numbers:
        if n not in used:
            used.add(n)
            continue
        if not layout.is_slot_folder(path):
            continue                    # the shared folders' own collisions: above
        highest += 1
        out.append(Found("repair_number",
                         f"\"Repair {n}\" in {_where(path)} (line {i + 1}) repeats a number used before it "
                         f"(repairable: Repair Saves & Logs numbers it Repair {highest})",
                         [("replace", path, i, f"Repair {highest}")],
                         ident=f"repair_number|{_where(path)}|{i}"))
    return out


def _where(path: Path) -> str:
    """A log file in a report: "<folder>\\<name>", "Save <S>\\<folder>\\<name>" for a slot's own in the
    older layout, "Save <S>\\Logs\\<folder>\\<name>" for one in the save's own folder."""
    slot = layout.is_slot_folder(path)
    own = slot and len(path.parents) > 3 and path.parents[1].name.lower() == layout.SAVE_LOGS.lower() \
        and path.parents[2].name.lower() == f"save {slot}" and path.parents[3].name.lower() == layout.SAVES.lower()
    return (f"Save {slot}\\" if slot else "") + (f"{layout.SAVE_LOGS}\\" if own else "") \
        + f"{path.parent.name}\\{path.name}"


def _notes(folder: Path, game: int, slot: int) -> list[Found]:
    import vv_log_additions as additions
    out = []
    people = additions.person_blocks(folder, slot, game)
    deaths: dict[tuple, list] = {}
    for b in people:
        if re.fullmatch(r"Death \d+", b.heading):
            deaths.setdefault(b.identity, []).append(b)
    # The Unaccounted records Remove false Unaccounted records takes out (v1.35.80): the note says so.
    try:
        removable = {(str(v.block.path), v.block.start) for v in false_unaccounted(folder, game, slot) if v.false}
    except (OSError, ValueError):
        removable = set()
    for b in people:
        if b.heading.startswith("Disappeared") and b.identity in deaths:
            out.append(Found("note", f"{b.identity[0]} has both a Death and a Disappeared record"))
        if b.heading.startswith("Unaccounted") and (b.value("What") or "").startswith("Left") \
                and b.identity in deaths:
            fix = (" (false: Repair Saves & Logs, Remove false Unaccounted records, takes it out)"
                   if (str(b.path), b.start) in removable else "")
            out.append(Found("note", f"{b.identity[0]} is Unaccounted (left the village) and has a Death record{fix}"))
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


# ---------------------------------------------------------------------------
# False Unaccounted records (v1.35.80)
# ---------------------------------------------------------------------------
#
# The owner's Kalahuna Tribe 2 (The Lost Children, Save 1): at 2026-10-20 09:22:01, the first load with
# the Elder Totems companion, the Unaccounted Villagers reconciliation (native/vvfp_cause_of_death/
# cod_roster.inc) matched the villagers of the last save by record number -- the totems had moved out of
# the table and every later villager loaded into another record -- and wrote 112 "Arrived" and 108 "Left"
# records of villagers who had only moved.  It now follows villagers by identity; the records already
# written are put right here, only on the player's word (Repair Saves & Logs, game closed, backup first,
# the Repairs log lists them), and only when the logs and the save CONTRADICT them by identity -- the
# name, sex, head and body (a "Name changed" record followed), with an age that fits:
#   LEFT   the same villager "Arrived" in the same reconciliation (one villager moved records); or in the
#          Village History snapshot of that save or the first after it; or a Death / Disappeared record;
#   ARRIVED  the same villager "Left" in the same reconciliation; or in the Village History snapshot
#          of the save before (the last one before it was found); or a Birth / Arrived record.
# Every other record -- nothing settles it, or two villagers could own the evidence -- is kept and listed
# with why.  Evidence is spent one to one: one villager settles one record.

UNACCOUNTED_HEAD = re.compile(r"^Unaccounted \d+\s*$")
FALSE_LABEL = "False Unaccounted records"
FALSE_REMOVE = "Remove them (each is listed with why it is false)"
FALSE_KEEP = "Keep them (changes nothing)"


@dataclass
class UnaccountedVerdict:
    block: object                      # vv_log_additions.Block
    left: bool                         # "Left the village" (else "Arrived")
    false: bool                        # contradicted: offered for removal
    reason: str


def _key(name: str | None, sex: str | None, head, body) -> tuple:
    return (name, (sex or "").strip().lower() or None, head, body)


def _int_or_none(v):
    try:
        return int(v) if v is not None else None
    except ValueError:
        return None


def _child_sex(b) -> str | None:
    """A Birth record's child's sex ("    Sex:" before the parents), or None."""
    for line in b.lines:
        if line.startswith("  Mother:") or line.startswith("  Father:"):
            break
        m = re.match(r"^    Sex: (\S+)", line)
        if m:
            return m.group(1)
    return None


def _record_fits(r, names: set, sex: str | None, head, body) -> bool:
    """A Birth record's child, or an Arrived record's villager, is one of `names` with these looks, and
    of this sex when both say."""
    import vv_log_additions as additions
    if additions.is_birth(r.heading):
        key, their_sex = _child(r), _child_sex(r)
    else:
        key, their_sex = r.identity, r.value("Sex")
    if not key or key[0] not in names or tuple(key[1:]) != (head, body):
        return False
    return not (sex and their_sex) or sex.strip().lower() == their_sex.strip().lower()


def false_unaccounted(folder: Path, game: int, slot: int) -> list[UnaccountedVerdict]:
    """Every Unaccounted record of this slot's village, judged by identity (above).  Reads only."""
    import vv_log_additions as additions
    folder = Path(folder)
    people = additions.person_blocks(folder, slot, game)
    unacc = [b for b in people if UNACCOUNTED_HEAD.match(b.heading)]
    if not unacc:
        return []
    # "Name changed": old (name, head, body) -> new name, and back.
    checker = tools.load_checker()
    villages = additions.current_villages(folder, game, slot)
    renamed: dict[tuple, str] = {}
    births_records: list = []
    for path in _births_paths(folder, game):
        for b in additions.blocks(path):
            if not b.of(slot, game, villages):
                continue
            if b.heading == "Name changed":
                head, body = b.int_value("Head"), b.int_value("Body")
                if b.value("Old name") and b.value("Name"):
                    renamed[(b.value("Old name"), head, body)] = b.value("Name")
            elif additions.is_birth(b.heading) or re.fullmatch(r"Arrived \d+", b.heading):
                births_records.append(b)

    def names_of(name: str | None, head, body) -> set:
        out, seen = {name}, set()
        while (name, head, body) in renamed and (name, head, body) not in seen:
            seen.add((name, head, body))
            name = renamed[(name, head, body)]
            out.add(name)
        return out

    def same(b, name, sex, head, body) -> bool:
        if b.int_value("Head") != head or b.int_value("Body") != body:
            return False
        if b.value("Sex") and sex and b.value("Sex").strip().lower() != sex.strip().lower():
            return False
        return b.value("Name") in names_of(name, head, body) or name in names_of(b.value("Name"), head, body)

    # The Village History snapshots of this village, by date.
    snapshots: dict[str, list] = {}
    for b in people:
        if b.heading.startswith("Villager ") and b.date and "History" in b.path.parent.name:
            snapshots.setdefault(b.date, []).append(b)
    dates = sorted(snapshots)
    deaths = [b for b in people if re.fullmatch(r"Death \d+", b.heading) or b.heading.startswith("Disappeared")]
    used: set[int] = set()               # id() of every piece of evidence spent

    def take(candidates) -> object | None:
        for c in candidates:
            if id(c) not in used:
                used.add(id(c))
                return c
        return None

    out: list[UnaccountedVerdict] = []
    verdict: dict[int, UnaccountedVerdict] = {}

    def info(b):
        return (b.value("Name"), b.value("Sex"), b.int_value("Head"), b.int_value("Body"),
                b.int_value("Age"), b.value("Found") or "", (b.value("What") or "").startswith("Left"))

    rows = [(b, *info(b)) for b in unacc]

    def fits(lrow, arow, prefs: bool, step: int | None) -> bool:
        """Arrived `arow` could be Left `lrow` moved to another record: one check, the same name (a rename
        followed), sex and looks (and likes and dislikes with `prefs`), the age gone on (by `step`)."""
        lb, name, sex, head, body, age, found, _l = lrow
        ab, _an, _as, _ah, _abody, aage, afound, _al = arow
        if afound != found or None in (age, aage, head, body) or aage < age or not same(ab, name, sex, head, body):
            return False
        if prefs and (ab.value("Likes"), ab.value("Dislikes")) != (lb.value("Likes"), lb.value("Dislikes")):
            return False
        return step is None or aage - age == step

    lefts = [r for r in rows if r[7]]
    arriveds = [r for r in rows if not r[7]]
    # The time every moved villager aged between the two saves of a check: the step most of the pairs
    # beyond doubt share (exactly one candidate on each side).
    steps: dict[str, int] = {}
    tally: dict[str, dict[int, int]] = {}
    for lrow in lefts:
        cands = [a for a in arriveds if fits(lrow, a, True, None)]
        if len(cands) == 1 and len([x for x in lefts if fits(x, cands[0], True, None)]) == 1:
            t = tally.setdefault(lrow[6], {})
            t[cands[0][5] - lrow[5]] = t.get(cands[0][5] - lrow[5], 0) + 1
    for found, t in tally.items():
        steps[found] = max(t, key=lambda k: (t[k], -k))
    # 1. One villager both "Left" and "Arrived" in one check: moved to another record -- only when the
    # pairing is beyond doubt, exactly one candidate on each side (Codex, #600: two villagers of one name,
    # sex, looks and likes are never paired by guess).
    paired: set[int] = set()
    for prefs in (True, False):
        for lrow in lefts:
            if id(lrow[0]) in paired:
                continue
            step = steps.get(lrow[6])
            cands = [a for a in arriveds if id(a[0]) not in paired and fits(lrow, a, prefs, step)]
            if len(cands) != 1:
                continue
            back = [x for x in lefts if id(x[0]) not in paired and fits(x, cands[0], prefs, step)]
            if len(back) != 1:
                continue
            b, a = lrow[0], cands[0][0]
            paired |= {id(b), id(a)}
            verdict[id(b)] = UnaccountedVerdict(b, True, True, f"the same villager \"Arrived\" in the same check "
                                                               f"({a.heading}): moved to another record")
            verdict[id(a)] = UnaccountedVerdict(a, False, True, f"the same villager \"Left\" in the same check "
                                                                f"({b.heading}): moved to another record")

    def namesake_in_check(row) -> object | None:
        """An unpaired record of the other kind in the same check with the same name, sex and looks: the
        evidence below could be that villager's, so it settles nothing."""
        b, name, sex, head, body, age, found, left = row
        for other in (arriveds if left else lefts):
            if id(other[0]) not in paired and other[6] == found and same(other[0], name, sex, head, body):
                return other[0]
        return None

    # 2. The rest, one by one.
    for row in rows:
        b, name, sex, head, body, age, found, left = row
        if id(b) in verdict:
            out.append(verdict[id(b)])
            continue
        if None in (head, body) or not name or age is None or not found:
            out.append(UnaccountedVerdict(b, left, False, "the record does not name the villager fully"))
            continue
        twin = namesake_in_check(row)
        if left:
            if twin is None:
                after = [d for d in dates if d >= found][:1]
                here = take(v for d in after for v in snapshots[d]
                            if same(v, name, sex, head, body) and v.int_value("Age") is not None
                            and v.int_value("Age") >= age)
                if here is not None:
                    out.append(UnaccountedVerdict(b, True, True, f"still in the village in the Village History "
                                                                 f"snapshot of {after[0]} ({here.heading}, age "
                                                                 f"{here.int_value('Age')})"))
                    continue
            gone = take(d for d in deaths if same(d, name, sex, head, body)
                        and (d.int_value("Age at death") is None or d.int_value("Age at death") >= age))
            if gone is not None:
                out.append(UnaccountedVerdict(b, True, True, f"has a {gone.heading.split(' ')[0]} record "
                                                             f"({gone.heading}, {gone.path.name})"))
                continue
            if twin is not None:
                out.append(UnaccountedVerdict(b, True, False, f"{twin.heading} in the same check has the same name, "
                                                              "sex and looks: which villager is which can not be told"))
                continue
            out.append(UnaccountedVerdict(b, True, False, "nothing in the logs or the save says where they went"))
        else:
            if twin is not None:
                out.append(UnaccountedVerdict(b, False, False, f"{twin.heading} in the same check has the same name, "
                                                               "sex and looks: which villager is which can not be told"))
                continue
            before = [d for d in dates if d < found][-1:]
            here = take(v for d in before for v in snapshots[d]
                        if same(v, name, sex, head, body) and v.int_value("Age") is not None
                        and v.int_value("Age") <= age)
            if here is not None:
                out.append(UnaccountedVerdict(b, False, True, f"already in the village in the Village History "
                                                              f"snapshot of {before[0]} ({here.heading}, age "
                                                              f"{here.int_value('Age')})"))
                continue
            # A Birth or Arrived record of this villager: the same name (a rename followed), head, body and
            # sex -- one record only; two that fit settle nothing (Codex, #600).
            fitting = [r for r in births_records if id(r) not in used and _record_fits(r, names_of(name, head, body),
                                                                                       sex, head, body)]
            if len(fitting) == 1:
                used.add(id(fitting[0]))
                out.append(UnaccountedVerdict(b, False, True, f"has a {fitting[0].heading} record "
                                                              f"({fitting[0].path.name})"))
                continue
            if len(fitting) > 1:
                out.append(UnaccountedVerdict(b, False, False, f"{len(fitting)} Birth / Arrived records fit: which "
                                                               "one is theirs can not be told"))
                continue
            out.append(UnaccountedVerdict(b, False, False, "nothing in the logs says how they came"))
    return out

def plan_false_unaccounted(folder: Path, game: int, slot: int):
    """Repair Saves & Logs' "Remove false Unaccounted records": every record false_unaccounted finds
    contradicted, listed with why, under one question per check that wrote them (the player may keep
    them all); the others kept and listed as notes."""
    import vv_log_additions as additions
    kind = additions.Kind("false_unaccounted", FALSE_LABEL)
    try:
        verdicts = false_unaccounted(folder, game, slot)
    except (OSError, ValueError) as exc:
        kind.notes.append(f"could not be read ({exc})")
        return kind
    groups: dict[str, list[UnaccountedVerdict]] = {}
    texts: dict[Path, list[str]] = {}
    for v in verdicts:
        b = v.block
        if not v.false:
            kind.notes.append(f"{b.heading} ({b.value('Name')}, {'Left' if v.left else 'Arrived'}, found "
                              f"{b.value('Found')}) is kept: {v.reason}")
            continue
        groups.setdefault(b.value("Found") or "", []).append(v)
    for found, items in sorted(groups.items()):
        key = f"false_unaccounted|{found}"
        listed = "; ".join(f"{v.block.heading} {v.block.value('Name')} ({'Left' if v.left else 'Arrived'}): "
                           f"{v.reason}" for v in items)
        kind.questions[key] = additions.Question(
            key, f"{len(items)} Unaccounted record(s) written at {found} are contradicted by who is in the "
                 f"village, the Village History and the Deaths and Births logs: {listed}. Remove them?",
            [FALSE_REMOVE, FALSE_KEEP], FALSE_REMOVE)
        for v in items:
            b = v.block
            if b.path not in texts:
                texts[b.path] = additions.read_lines(b.path)
            kind.removes.append(additions.Remove(b.path, b.start, _end_with_blank(texts[b.path], b) - b.start + 1,
                                                 key, FALSE_REMOVE))
    return kind


def left_alone(folder: Path, game: int, slot: int) -> set[str]:
    """The contradictions the player chose to leave in the past records."""
    import vv_log_decisions
    return vv_log_decisions.left_alone(Path(folder), game, slot)


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
    """Every contradiction the player answered "Retroactively edit records?" No to, added to the
    slot's decisions (src/vv_log_decisions.py).  Returns the new ones."""
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
    import vv_log_decisions
    return vv_log_decisions.remember_left(Path(folder), game, slot, idents)
