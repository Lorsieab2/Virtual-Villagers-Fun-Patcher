"""The player's decisions about contradictions in the logs, kept when they chose not to edit the old
records (all five games).

The owner (2026-10-10): every contradiction Repair Saves & Logs asks about is followed by
"Retroactively edit records?".  Yes: the old records are corrected (a copy in Copies Made Before
Repairs first, a Repairs Made entry).  No: the log is left exactly as it is, and the decision is
remembered here, so the Family Tree Maker, the Village Matchmaker, the last-names window and Check
Logs still follow the player's answer.

THE FILE.  One per game and save slot, beside the repair approvals:

    <save folder>\\Virtual Villagers Fun Patcher Data\\Log Checks\\
        Virtual Villagers <game> Log Decisions - Save <slot>.json

("Cross-Check" in older builds: src/vv_save_layout.py), UTF-8 JSON:

    {"version": 1,
     "decisions": [
       {"kind": "born_arrived",              -- what was contradicted (one kind per question family)
        "village": "Village: <name> (Save n)",
        "name": "Cheop Bahati", "head": 4, "body": 15,   -- the villager the decision is about
        "verdict": "remove",                 -- the player's answer: what the record should be
        "edited": false,                     -- false: the old record was left as it is
        "date": "2026-10-10 01:02:03"}]}

A later decision about the same kind, village and villager replaces the earlier one.  Written
through a temporary file moved into place; a file that cannot be read is treated as holding no
decisions (and is never overwritten by a reader).  Each decision names its village's header, and
readers pass the headers the slot's current village has had, so a new village after Start Over
never inherits the previous one's decisions.

Readers ask `decided(folder, game, slot, kind, verdict)` for the set of (name, head, body) the player
gave that verdict for.

ONE STORE.  The contradictions Repair Saves & Logs found in the records themselves (a Death or Repair
number used twice, a backfilled record of a villager already recorded) were remembered in a second
file, a text file of one line each, "Virtual Villagers <game> Contradictions Left - Save <slot>.txt".
Both answers are the same thing -- "Retroactively edit records?" No -- so they are now kept here,
as decisions of the kind "contradiction_left" whose "field" is the contradiction's identity
(src/vv_log_contradictions.py).  The text file is still READ (left_alone), so an answer given before
this version still holds, and every one of its lines is copied into this file the first time a new
answer is written; it is never deleted or rewritten, and nothing is written to it any more.

ANSWERED QUESTIONS (v1.35.80).  Every real answer to Repair Saves & Logs' questions is kept here too, as
the kind "answered" (src/vv_answered_questions.py), and every rename the patcher makes as the kind
"answered_alias" (ALIAS_KIND, src/vv_last_names.py), so each decision and answer follows its villager.
Only the player's change or clear in Answered questions, and Repair moving a reconciliation answer from
its pre-v1.35.80 id to its new one (the same answer and date), rewrite the file (`rewrite`).
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

import vv_save_layout as layout

VERSION = 1
RELATIVE = layout.DATA + r"\Log Checks\Virtual Villagers {game} Log Decisions - Save {slot}.json"
# The earlier second store (read, never written): one contradiction identity per line.
LEGACY_LEFT = layout.DATA + r"\Log Checks\Virtual Villagers {game} Contradictions Left - Save {slot}.txt"
LEFT_KIND = "contradiction_left"


def path(folder: Path, game: int, slot: int) -> Path:
    """Where the slot's decisions are: an older build's "Cross-Check" folder while only it exists."""
    return layout.route(Path(folder), RELATIVE.format(game=game, slot=slot))


def load(folder: Path, game: int, slot: int) -> list[dict]:
    try:
        data = json.loads(path(folder, game, slot).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(data, dict) or data.get("version") != VERSION or not isinstance(data.get("decisions"), list):
        return []
    return [d for d in data["decisions"] if isinstance(d, dict)]


def decided(folder: Path, game: int, slot: int, kind: str, verdict: str,
            villages: set[str] | None = None) -> set[tuple]:
    """(name, head, body) of every villager the player gave `verdict` about `kind` -- for one of
    `villages` (the headers the slot's current village has had), when given."""
    out = set()
    found = load(folder, game, slot)
    renamed = aliases(found)
    for d in found:
        if d.get("kind") == kind and d.get("verdict") == verdict \
                and (villages is None or d.get("village") in villages):
            who = (d.get("name"), d.get("head"), d.get("body"))
            out.add(who)
            # ...and the villager under every name the patcher has given them since (Last Names, Number
            # Duplicate Names, cut names restored): the decision follows the villager.
            out.add(forward(who, renamed))
    return out


# The renames the patcher made (src/vv_last_names.py plan_renames), kept so that every decision and
# answer follows its villager: {"kind": "answered_alias", "name": <old>, "head": h, "body": b,
# "field": <new name>, "verdict": "renamed", "date": ...}.  Only ever added.
ALIAS_KIND = "answered_alias"


def aliases(decisions: list[dict]) -> dict[tuple, tuple]:
    """(old name, head, body) -> (new name, head, body), from the renames kept in `decisions`."""
    out = {}
    for d in decisions:
        if d.get("kind") == ALIAS_KIND and isinstance(d.get("name"), str) and isinstance(d.get("field"), str):
            out[(d["name"], d.get("head"), d.get("body"))] = (d["field"], d.get("head"), d.get("body"))
    return out


def forward(who: tuple, renamed: dict[tuple, tuple]) -> tuple:
    """`who` under the latest name the patcher's renames gave them (a chain of renames followed; a
    loop stops where it began)."""
    seen = {who}
    while who in renamed:
        who = renamed[who]
        if who in seen:
            break
        seen.add(who)
    return who


def record(folder: Path, game: int, slot: int, entries: list[dict], now: datetime | None = None) -> Path:
    """Add the decisions `entries` (kind, village, name, head, body, verdict, edited), each replacing an
    earlier one about the same kind, village and villager.  Returns the file."""
    target = path(folder, game, slot)
    kept = load(folder, game, slot)
    when = (now or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")

    def same(a: dict, b: dict) -> bool:
        # "field": a grave decision is about one field of the grave (src/vv_graves.py); the other kinds
        # have none, so they still replace one decision per villager.
        return all(a.get(k) == b.get(k) for k in ("kind", "village", "name", "head", "body", "field"))

    for entry in entries:
        entry = {**entry, "date": when}
        kept = [d for d in kept if not same(d, entry)] + [entry]
    target.parent.mkdir(parents=True, exist_ok=True)
    _set_aside_unreadable(target)
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_bytes(json.dumps({"version": VERSION, "decisions": kept}, indent=1).encode("utf-8"))
    os.replace(temporary, target)
    return target


def rewrite(folder: Path, game: int, slot: int, change) -> Path | None:
    """Replace the decisions with `change(decisions)` (a new list), through a temporary file moved into
    place.  Used only when the player changes or clears an answer in Repair Saves & Logs' Answered
    questions (src/vv_answered_questions.py).  A file that is there and cannot be read is never
    rewritten: None, nothing changed."""
    target = path(folder, game, slot)
    if target.is_file():
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(data, dict) or data.get("version") != VERSION or not isinstance(data.get("decisions"), list):
            return None
    kept = change(load(folder, game, slot))
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_bytes(json.dumps({"version": VERSION, "decisions": kept}, indent=1).encode("utf-8"))
    os.replace(temporary, target)
    return target


def encode(decisions: list[dict]) -> bytes:
    """The file's bytes for `decisions` (as `record` writes them)."""
    return json.dumps({"version": VERSION, "decisions": decisions}, indent=1).encode("utf-8")


def _set_aside_unreadable(target: Path) -> None:
    """A decisions file that is there and cannot be read is moved aside (".unreadable", numbered when
    that name is taken) before a new one is written, never written over: what it held may be
    recoverable by hand."""
    if not target.is_file():
        return
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("version") == VERSION and isinstance(data.get("decisions"), list):
            return
    except (OSError, ValueError):
        pass
    k = 0
    while True:
        aside = target.with_name(target.name + (".unreadable" if k == 0 else f".unreadable{k}"))
        if not aside.exists():
            break
        k += 1
    try:
        os.replace(target, aside)
    except OSError:
        pass


def legacy_left(folder: Path, game: int, slot: int) -> set[str]:
    """The contradictions the earlier text file says the player chose to leave (read only)."""
    path = layout.route(Path(folder), LEGACY_LEFT.format(game=game, slot=slot))
    try:
        return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}
    except OSError:
        return set()


def left_alone(folder: Path, game: int, slot: int) -> set[str]:
    """The contradictions the player chose to leave in the past records ("Retroactively edit
    records?" No), from this file and from the earlier text file."""
    return legacy_left(folder, game, slot) | {
        str(d["field"]) for d in load(folder, game, slot)
        if d.get("kind") == LEFT_KIND and isinstance(d.get("field"), str) and d["field"]}


def remember_left(folder: Path, game: int, slot: int, idents: list[str], now: datetime | None = None) -> list[str]:
    """Add contradiction identities to the decisions.  Returns those that were not known before.
    The earlier text file's lines come along the first time something is written."""
    known = left_alone(folder, game, slot)
    new = [i for n, i in enumerate(idents) if i not in known and i not in idents[:n]]
    if not new:
        return []
    carried = sorted(legacy_left(folder, game, slot) - {str(d.get("field")) for d in load(folder, game, slot)
                                                       if d.get("kind") == LEFT_KIND})
    record(folder, game, slot,
           [{"kind": LEFT_KIND, "field": i, "verdict": "leave", "edited": False} for i in carried + new], now)
    return new
