"""Number Duplicate Names: villagers who share a name, numbered in the game and in the logs (all five games).

The owner (2026-10-07): "How about a "Number duplicate names" button in the family tree maker and repair
logs?  If there are duplicate "Soda"s, name the first one "Soda I", and the second one "Soda II" etc.
Also offer to edit the save files."

Everyone the save and the logs know is numbered, the dead too, oldest first unless the player
picks another order (vv_genealogy's duplicate_names and NUMBER_ORDERS, as the Family Tree Maker
shows them): the living are renamed in the save, and every
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
              nameless: set[str] = frozenset(), bodies: set[tuple] = frozenset(),
              taken: set[str] = frozenset(), order: str = "oldest") -> Numbering:
    """The numbered name of each villager the save and the logs can tell apart.  `alike`: each
    (name, head, body) the save holds more than once, and how many times; `nameless`: the names of
    records that do not say how their villager looks; `bodies`: the (name, head, body) of the dead
    lying in the save; `taken`: names the patcher's own files hold (never given again)."""
    out = Numbering()
    alike = alike or {}
    for (name, _head, _body), count in sorted(alike.items()):
        out.notes.append(f"{count} living villagers are called {name} and look the same, so the records cannot "
                         "tell them apart: they keep their name.")
    # A namesake known only from records -- neither in the save nor recorded as dead or gone -- may be
    # a living namesake before Change Appearance (Codex, #557): that record keeps its name and is not
    # counted, so the villagers the save holds are numbered among themselves.
    living_names = {p.name for p in village.known() if p.alive}
    unsure = {p.id for p in village.known() if p.name in living_names and not p.alive and not p.gone
              and p.head is not None and p.body is not None and p.key not in bodies}
    weight = {p.id: alike[p.key] for p in village.known() if p.key in alike}
    numbered = gen.duplicate_names(village, order, reserved=set(nameless) | set(taken), leave=unsure,
                                   weight=weight)
    for name in sorted(nameless & {p.name for p in village.known()}):
        out.notes.append(f"Older records name a {name} without saying how they look, so those records keep "
                         f"the name {name}.")
    for pid in sorted(unsure, key=lambda q: village.people[q].key):
        name, head, body = village.people[pid].key
        if name in {village.people[q].name for q in numbered}:
            out.notes.append(f"An older record of {name} (head {head}, body {body}) has looks no living {name} has; "
                             f"it may be one of them before Change Appearance, so it keeps the name {name}.")
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


def evidence(folder: Path, game: int, slot: int) -> tuple[dict[tuple, int], set[str], set[tuple], set[str]]:
    """What the family tree's reading merges or drops: each name, head and body more than one
    villager has -- in the save, living or a body, and in the Death and Disappeared records -- the
    names of log records without looks, the dead lying in the save, and the names in the patcher's
    statistics roster and Village Elders, which this renames too (Codex, #557)."""
    import vv_log_additions as additions
    everyone = ln.living(folder, game, slot, bodies=True)
    alive = {v.at for v in ln.living(folder, game, slot)}
    counts = Counter(v.identity for v in everyone)
    blocks = additions.person_blocks(folder, slot, game)
    counts.update(b.identity for b in blocks if b.heading.startswith(("Death", "Disappeared"))
                  and b.identity[1] is not None and b.identity[2] is not None)
    nameless = {b.identity[0] for b in blocks
                if b.identity[0] and (b.identity[1] is None or b.identity[2] is None)}
    taken = set()
    data_dir = Path(folder) / ln.tools.DATA
    for path, columns in ((data_dir / "Village Statistics" / f"Village Roster - Save {slot}.dat", (1,)),
                          (data_dir / "Village Elders" / f"Village Elders - Save {slot}.dat", (2, 3, 4))):
        try:
            lines = path.read_bytes().decode("latin-1").split("\n")
        except OSError:
            continue
        for line in lines:
            parts = line.rstrip("\r").split("\t")
            if path.name.startswith("Village Elders") and parts[0] != "E":
                continue
            taken.update(parts[c] for c in columns if c < len(parts) and parts[c])
    return ({key: n for key, n in counts.items() if n > 1}, nameless,
            {v.identity for v in everyone if v.at not in alive}, taken)


def number_names(folder: Path, game: int, slot: int, order: str = "oldest",
                 processes: vv_save_backup.ProcessController | None = None,
                 now: datetime | None = None) -> tuple[ln.Result, Numbering]:
    """Number every duplicate name in the save, the logs and the patcher's files.  Refused (nothing
    changed) while the game runs or when no name is shared."""
    folder = Path(folder)
    controller = processes if processes is not None else vv_save_backup.WindowsProcesses()
    ln.tools._refuse_if_running(folder, controller)
    import vv_log_additions as additions
    if additions.current_villages(folder, game, slot) is None:   # records of an erased village (Codex, #557)
        raise ln.LastNamesError("The save's tribe name could not be read, so this village's records cannot be "
                                "told from an earlier village's; nothing was changed.")
    try:
        wanted = numbering(gen.load_village(folder, game, slot), *evidence(folder, game, slot), order=order)
        work = ln.plan_renames(folder, game, slot, wanted.renames, dead=True)
        wanted.notes += work.notes
    except (gen.GenealogyError, struct.error, ValueError, OSError) as exc:
        raise ln.LastNamesError(f"A file could not be read ({exc}); nothing was changed.") from exc
    if not work.renames:
        raise ln.LastNamesError(" ".join(wanted.notes) or "No two villagers share a name.")
    return ln.apply(folder, work, controller, now, BACKUP_LABEL, "numbering the names"), wanted
