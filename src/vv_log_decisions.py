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
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

import vv_save_layout as layout

VERSION = 1
RELATIVE = layout.DATA + r"\Log Checks\Virtual Villagers {game} Log Decisions - Save {slot}.json"


def path(folder: Path, game: int, slot: int) -> Path:
    """Where the slot's decisions are: an older build's "Cross-Check" folder while only it exists."""
    return layout.find(Path(folder), RELATIVE.format(game=game, slot=slot))


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
    for d in load(folder, game, slot):
        if d.get("kind") == kind and d.get("verdict") == verdict \
                and (villages is None or d.get("village") in villages):
            out.add((d.get("name"), d.get("head"), d.get("body")))
    return out


def record(folder: Path, game: int, slot: int, entries: list[dict], now: datetime | None = None) -> Path:
    """Add the decisions `entries` (kind, village, name, head, body, verdict, edited), each replacing an
    earlier one about the same kind, village and villager.  Returns the file."""
    target = path(folder, game, slot)
    kept = load(folder, game, slot)
    when = (now or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")

    def same(a: dict, b: dict) -> bool:
        return all(a.get(k) == b.get(k) for k in ("kind", "village", "name", "head", "body"))

    for entry in entries:
        entry = {**entry, "date": when}
        kept = [d for d in kept if not same(d, entry)] + [entry]
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_bytes(json.dumps({"version": VERSION, "decisions": kept}, indent=1).encode("utf-8"))
    os.replace(temporary, target)
    return target
