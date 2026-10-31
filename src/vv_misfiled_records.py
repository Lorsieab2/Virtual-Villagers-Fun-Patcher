"""Repair Saves & Logs: records written into ANOTHER save's log, moved to their own (all five games).

A record the parentage companion makes before the village on screen has been saved is HELD and written
at the next save (native/parentage_export/parentage_export.c emit_record).  Until 2026-10-31 it was
written under THAT save's village, whichever village it was made in: the owner's Secret City, Save 1's
Births and Conceptions log, holds Conception 312 (Mother Kiwi Jumapili, Father Motu Okelani) and
Conception 316 (Mother Matate Jumapili, Father Motu Okelani) -- Save 2's villagers only -- written at
Save 1's save on 2026-10-31 15:18:45.  The companion now keeps each held record for the save that was
loaded when it was made; this step puts right what older builds already wrote (the owner, 2026-10-31:
"move 312 and 316 into Save 2's log").

What is moved, and only this: a record in a slot's OWN log folder that carries the held record's note
("  Note: Recorded before this village was saved, ...") and whose every named villager (Mother, Father,
Child, or the record's own Name) is found in exactly ONE other slot's village -- its save, the save's
older generations, its Village History snapshots or its Village Population page -- with the same name,
head, body, likes and dislikes (and sex, where both say), and in no other slot, this one included.
Nothing is guessed:

* a villager found in no slot (the game's pre-tribe simulation: Bikini, Piko, Aipi...) leaves the
  record where it is, untouched;
* a villager found in two slots (a copied village) leaves it where it is, with a note;
* a record with no villager it can read leaves it where it is.

The player is asked about each one (Move it / Leave it where it is), as every other Repair step asks.
Moving appends the record -- its own text and number, unchanged, plus one Note line saying where it
came from -- to the end of the other slot's own log of the same kind (a new numbered file when the
last is full, src/vv_save_layout.py append_target), and only after that file is written is the record
taken out of the wrong log (vv_log_additions.apply writes the destinations first).  Both files are
copied into Data\\Copies Made Before Repairs first, and the save folder is backed up before any Repair.
Numbers are kept: Conception, Birth, Death and Island event numbers are the GAME's running count, read
across every slot's folder, so a record keeps its number in its new log and no other record changes.
"""
from __future__ import annotations

import re
from pathlib import Path

import vv_log_additions as additions
import vv_save_layout as layout

KIND_ID = "misfiled"
LABEL = "Records written into another save's log (moved to their own save's log)"
MOVE_IT = "Move it to its own save's log"
LEAVE_IT = "Leave it where it is"
HELD_NOTE = "  Note: Recorded before this village was saved"

# The logs a held record can be in: (the Logs sub-folder, the file stem after "Virtual Villagers <n> ",
# the marker the companion counts a file's records by -- append_target rolls at 256 of them).
FAMILIES = (
    ("Births and Conceptions", "Births and Conceptions Log", "Conception "),
    ("Deaths and Disappearances", "Deaths Log", "Death "),
    ("Island Events", "Island Events Log", "Island event "),
    ("Unaccounted Villagers", "Unaccounted Villagers Log", "Unaccounted "),
)
PEOPLE = ("Mother", "Father", "Child")


def moved_note(slot: int) -> str:
    return (f"  Note: Moved here from Save {slot}'s log by Repair Saves & Logs (it was written there by "
            "mistake, at that save)")


def _people(b: additions.Block) -> list[tuple[str, object]]:
    """The villagers a record names, each (its label, a vv_reconcile.Seen): its Mother, Father and Child
    (with their own lines indented under them), or the record's own Name.  A named villager with no
    Head, Body, Likes or Dislikes line can not be told apart: then nothing (the record stays)."""
    import vv_reconcile as rc
    out = []
    for label in PEOPLE:
        if any(line.startswith(f"  {label}:") for line in b.lines):
            person = rc._sub_person(b.lines, label)
            if person is None:
                continue                                # "(unknown)", "(none)": no villager named
            out.append((label, person))
    if not out and b.value("Name"):
        out.append(("Name", rc.Seen(b.value("Name"), b.int_value("Head"), b.int_value("Body"), b.value("Sex"),
                                    None, rc._words(b.value("Likes")), rc._words(b.value("Dislikes")))))
    if any(p.head is None or p.body is None or p.likes is None or p.dislikes is None for _label, p in out):
        return []
    return out


def _age_at(b: additions.Block, label: str) -> int | None:
    """A Conception's "Age at conception" under its Mother / Father."""
    inside = False
    for line in b.lines:
        if line.startswith(f"  {label}:"):
            inside = True
            continue
        if inside:
            if not line.startswith("    "):
                break
            if line.strip().startswith("Age at conception:"):
                try:
                    return int(line.split(":", 1)[1].strip().split()[0])
                except (ValueError, IndexError):
                    return None
    return None


def roster(folder: Path, game: int, slot: int) -> list:
    """Everyone slot `slot`'s village has had: its save and the save's older generations (the living
    and the bodies), its Village History snapshots and its Village Population page (only under its own
    village's headers, src/vv_log_additions.py current_villages).  Empty when the slot has nothing."""
    import vv_reconcile as rc
    folder = Path(folder)
    people: list = []
    for path in rc.save_generations(folder, game, slot):
        try:
            alive, bodies = rc.read_save(path, game)
        except (rc.ReconcileError, OSError, ValueError):
            continue
        people += alive + bodies
    villages = additions.current_villages(folder, game, slot)
    try:
        logs = rc.read_logs(folder, game, slot, villages)
    except OSError:
        return people
    for census in logs.censuses:
        people += census.people
    return people


def _same(p, r, strict: bool) -> bool:
    """Whether roster entry `r` is the villager `p` a record names.  `strict`: the very same likes and
    dislikes (to MOVE a record); otherwise also one list within the other, as an older roster that
    printed only each villager's first word shows them (to rule a slot OUT, the safe direction)."""
    import vv_reconcile as rc
    if p.name != r.name or p.head != r.head or p.body != r.body:
        return False
    if p.sex is not None and r.sex is not None and p.sex != r.sex:
        return False
    if strict:
        return p.likes == r.likes and p.dislikes == r.dislikes
    return rc._compatible(p.likes, r.likes) and rc._compatible(p.dislikes, r.dislikes)


def _own_logs(folder: Path, game: int, slot: int) -> list[tuple[Path, str, str, str]]:
    """The slot's OWN log files a held record can be in: (file, sub-folder, stem, marker)."""
    out = []
    for sub, stem_tail, marker in FAMILIES:
        stem = f"Virtual Villagers {game} {stem_tail}"
        for path in layout.numbered_logs(folder, sub, stem, slot):
            if layout.is_slot_folder(path) == slot:
                out.append((path, sub, stem, marker))
    return out


def stem_of(path: Path) -> str:
    """"Virtual Villagers 3 Births and Conceptions Log" of "... Log 7.txt"."""
    return re.sub(r" \d+\.txt$", "", path.name)


def _already_there(folder: Path, game: int, home: int, sub: str, stem: str, b: additions.Block) -> bool:
    """Whether the other slot's own logs of this kind already hold this record, moved there before."""
    for path in layout.numbered_logs(folder, sub, stem, home):
        if layout.is_slot_folder(path) != home:
            continue
        try:
            found = additions.blocks(path)
        except OSError:
            continue
        for other in found:
            if other.lines[:len(b.lines)] == b.lines and any(line.startswith("  Note: Moved here from Save ")
                                                            for line in other.lines[len(b.lines):]):
                return True
    return False


def _end(lines: list[str], b: additions.Block) -> int:
    """How many lines the record takes out: its own, and the blank line after it."""
    count = len(b.lines)
    after = b.start + count
    if after < len(lines) and not lines[after].strip():
        count += 1
    return count


def plan(folder: Path, game: int, slot: int, rosters: dict | None = None) -> additions.Kind:
    """The held records in this slot's own logs whose villagers are another slot's village only, each a
    question (Move it / Leave it where it is) with the record it adds there and the record it takes out
    here.  Reads only.  `rosters`: slot -> roster (tests)."""
    folder = Path(folder)
    kind = additions.Kind(KIND_ID, LABEL)
    files = _own_logs(folder, game, slot)
    held = []
    for path, sub, stem, marker in files:
        try:
            lines = additions.read_lines(path)
        except OSError:
            continue
        for b in additions.blocks(path, lines):
            if any(line.startswith(HELD_NOTE) for line in b.lines) and not b.heading.startswith("Village:"):
                held.append((path, sub, stem, marker, lines, b))
    if not held:
        return kind
    if rosters is None:
        rosters = {s: roster(folder, game, s) for s in layout.SLOTS}
    targets: dict[tuple[int, str], tuple[Path, int, str]] = {}
    for path, sub, stem, marker, lines, b in held:
        people = _people(b)
        if not people:
            continue
        homes: set[int] = set()
        clear = True
        for _label, person in people:
            loose = {s for s, found in rosters.items() if any(_same(person, r, False) for r in found)}
            strict = {s for s, found in rosters.items() if any(_same(person, r, True) for r in found)}
            if len(loose) != 1 or loose != strict or slot in loose:
                clear = False
                if len(loose) > 1 and slot not in loose:
                    kind.notes.append(f"{b.heading} in Save {slot}'s log: {person.described()} is in "
                                      f"{len(loose)} saves' villages, so which one it belongs to can not be "
                                      "told. It is left where it is.")
                break
            homes |= strict
        if not clear or len(homes) != 1:
            continue
        home = next(iter(homes))
        # A Conception: no parent younger than when the other village first had them.
        for label, person in people:
            age = _age_at(b, label)
            if age is not None and not any(_same(person, r, True) and (r.age is None or r.age <= age)
                                           for r in rosters[home]):
                clear = False
        if not clear:
            continue
        if (home, sub) not in targets:
            target = layout.append_target(folder, sub, stem, home, marker)
            villages = additions.current_villages(folder, game, home)
            import vv_answered_questions
            header = vv_answered_questions.village_header(folder, game, home)
            anchor, lead = additions._append_point(target, home, game, villages, header)
            targets[(home, sub)] = (target, anchor, lead)
        target, anchor, lead = targets[(home, sub)]
        # Only the first record appended needs the separation and the header: the rest follow it.
        if any(i.path == target for i in kind.inserts):
            lead = ""
        who = ", ".join(p.name if label == "Name" else f"{label} {p.name}" for label, p in people)
        key = f"{KIND_ID}|{path.name}|{b.start}"
        kind.questions[key] = additions.Question(
            key, f"{b.heading} ({who}) is in Save {slot}'s {sub} log, but its villagers are Save {home}'s "
                 f"only. Move it to the end of Save {home}'s {sub} log (it keeps its number)?",
            [MOVE_IT, LEAVE_IT], MOVE_IT,
            f"{b.heading}|Save {slot}->Save {home}", tuple((p.name, p.head, p.body) for _label, p in people))
        text = lead + "\n".join(b.lines) + "\n" + moved_note(slot) + "\n"
        if not _already_there(folder, game, home, sub, stem_of(path), b):
            kind.inserts.append(additions.Insert(target, anchor, len(kind.inserts), question=key,
                                                 by_answer={MOVE_IT: text}))
        # Already in its own save's log (a move whose second half did not happen): only taken out here.
        kind.removes.append(additions.Remove(path, b.start, _end(lines, b), key, MOVE_IT))
    return kind
