"""Number Duplicate Names: villagers who share a name, numbered in the game and in the logs (all five games).

The owner (2026-10-07): "How about a "Number duplicate names" button in the family tree maker and repair
logs?  If there are duplicate "Soda"s, name the first one "Soda I", and the second one "Soda II" etc.
Also offer to edit the save files."

Everyone the save and the logs know is numbered, the dead too, oldest first (vv_genealogy's
duplicate_names, as the Family Tree Maker shows them): the living are renamed in the save, and every
record naming any of them -- their own and as a parent -- in the logs and the patcher's own files,
through Last Names' renaming (vv_last_names.plan_renames), with its safety: the game must be closed,
the save folder is backed up first ("(before numbering names)"), every file is swapped in and read
back, and any failure puts every changed file back.

A villager is told apart by name, head and body.  Two namesakes who also share their looks cannot be
told apart in the logs, so they are left as they are (and said so), as is a name the game has no
room for.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import vv_genealogy as gen
import vv_last_names as ln
import vv_save_backup

BACKUP_LABEL = "(before numbering names)"


@dataclass
class Numbering:
    renames: dict[tuple, str] = field(default_factory=dict)    # (name, head, body) -> numbered name
    notes: list[str] = field(default_factory=list)              # who is left as they are, and why


def numbering(village: gen.Village) -> Numbering:
    """The numbered name of each villager the save and the logs can tell apart."""
    out = Numbering()
    by_key: dict[tuple, list[str]] = {}
    for pid, new in gen.duplicate_names(village).items():
        by_key.setdefault(village.people[pid].key, []).append(new)
    for (name, head, body), news in sorted(by_key.items(), key=lambda item: item[1]):
        if len(news) > 1:
            out.notes.append(f"{' and '.join(news)} are called {name} and look the same, so the records cannot "
                             "tell them apart: they keep their name.")
        elif head is None or body is None:
            out.notes.append(f"{news[0]}'s records do not say how they look, so they keep their name.")
        elif len(news[0]) > ln.ROOM[village.game]:
            out.notes.append(f"{news[0]} is longer than the game's {ln.ROOM[village.game]} characters, so "
                             f"{name} keeps their name.")
        else:
            out.renames[(name, head, body)] = news[0]
    return out


def number_names(folder: Path, game: int, slot: int,
                 processes: vv_save_backup.ProcessController | None = None,
                 now: datetime | None = None) -> tuple[ln.Result, Numbering]:
    """Number every duplicate name in the save, the logs and the patcher's files.  Refused (nothing
    changed) while the game runs or when no name is shared."""
    folder = Path(folder)
    controller = processes if processes is not None else vv_save_backup.WindowsProcesses()
    ln.tools._refuse_if_running(folder, controller)
    try:
        wanted = numbering(gen.load_village(folder, game, slot))
        work = ln.plan_renames(folder, game, slot, wanted.renames, dead=True)
    except (gen.GenealogyError, struct.error, ValueError, OSError) as exc:
        raise ln.LastNamesError(f"A file could not be read ({exc}); nothing was changed.") from exc
    if not work.renames:
        raise ln.LastNamesError(" ".join(wanted.notes) or "No two villagers share a name.")
    return ln.apply(folder, work, controller, now, BACKUP_LABEL, "numbering the names"), wanted
