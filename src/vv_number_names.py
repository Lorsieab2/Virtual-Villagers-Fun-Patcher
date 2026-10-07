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

A villager is told apart by name, head and body.  Two living namesakes who also share their looks
cannot be told apart in the records (the save shows them; the family tree sees one), so they are left
as they are and the player is told, as for a name the game has no room for, a record that does not
say how its villager looks, and any line in a log or the patcher's files that names a numbered
villager without their looks (Codex, #557).
"""
from __future__ import annotations

import struct
from collections import Counter
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


def numbering(village: gen.Village, alike: dict[tuple, int] | None = None,
              nameless: set[str] = frozenset()) -> Numbering:
    """The numbered name of each villager the save and the logs can tell apart.  `alike`: each
    (name, head, body) the save holds more than once, and how many times; `nameless`: the names of
    records that do not say how their villager looks."""
    out = Numbering()
    alike = alike or {}
    for (name, _head, _body), count in sorted(alike.items()):
        out.notes.append(f"{count} living villagers are called {name} and look the same, so the records cannot "
                         "tell them apart: they keep their name.")
    numbered = gen.duplicate_names(village)
    for name in sorted(nameless & {p.name for p in village.known()}):
        out.notes.append(f"Older records name a {name} without saying how they look, so those records keep "
                         f"the name {name}.")
    for pid, new in sorted(numbered.items(), key=lambda item: item[1]):
        name, head, body = village.people[pid].key
        if (name, head, body) in alike:
            continue
        if head is None or body is None:
            out.notes.append(f"{new}'s records do not say how they look, so they keep the name {name}.")
        elif len(new) > ln.ROOM[village.game]:
            out.notes.append(f"{new} is longer than the game's {ln.ROOM[village.game]} characters, so "
                             f"{name} keeps their name.")
        else:
            out.renames[(name, head, body)] = new
    return out


def _evidence(folder: Path, game: int, slot: int) -> tuple[dict[tuple, int], set[str]]:
    """What the family tree's reading merges or drops: the living records the save holds more than
    once (by name, head and body), and the names of log records without looks."""
    import vv_log_additions as additions
    counts = Counter(v.identity for v in ln.living(folder, game, slot))
    nameless = {b.identity[0] for b in additions.person_blocks(folder, slot, game)
                if b.identity[0] and (b.identity[1] is None or b.identity[2] is None)}
    return {key: n for key, n in counts.items() if n > 1}, nameless


def number_names(folder: Path, game: int, slot: int,
                 processes: vv_save_backup.ProcessController | None = None,
                 now: datetime | None = None) -> tuple[ln.Result, Numbering]:
    """Number every duplicate name in the save, the logs and the patcher's files.  Refused (nothing
    changed) while the game runs or when no name is shared."""
    folder = Path(folder)
    controller = processes if processes is not None else vv_save_backup.WindowsProcesses()
    ln.tools._refuse_if_running(folder, controller)
    try:
        wanted = numbering(gen.load_village(folder, game, slot), *_evidence(folder, game, slot))
        work = ln.plan_renames(folder, game, slot, wanted.renames, dead=True)
        wanted.notes += work.notes
    except (gen.GenealogyError, struct.error, ValueError, OSError) as exc:
        raise ln.LastNamesError(f"A file could not be read ({exc}); nothing was changed.") from exc
    if not work.renames:
        raise ln.LastNamesError(" ".join(wanted.notes) or "No two villagers share a name.")
    return ln.apply(folder, work, controller, now, BACKUP_LABEL, "numbering the names"), wanted
