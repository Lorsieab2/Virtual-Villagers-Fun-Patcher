"""Names the game's Villager Details screen cut short, matched to the full names the logs keep (all five games).

The stock games' Villager Detail screen cuts a villager's name when the screen is closed: A New Home
keeps 10 characters, the others 18, and a very wide name fewer (measured live, 2026-10-07).  The
cut name ends up in the save, and so in every log written after it.  The owner (2026-10-07) wants a
safeguard:

    "Full names will be in the logs.  Any truncated in-game name will be matched to the correct
    villager in the logs using as much data as possible.  Family trees will use the full names from
    the logs, then the save data."

and "the repair logs thing should repair cut-off names from the last save/log".

A living villager whose name could have been cut (no longer than the screen keeps) is matched to a
LONGER name the logs record for a villager who is not dead, disappeared, gone or unaccounted for,
with everything that can be compared agreeing:

  * the full name starts with the save's name, and fits the game's own name field (vv_last_names.ROOM);
  * the same head and body (a villager is told apart by name, head and body);
  * the same sex, where the logs say one;
  * the same likes and dislikes, where the logs record them under both names (the logs print each
    as words, so the records under the cut name are compared with those under the full one);
  * no other living villager has the full name.

Exactly one such name is the villager's; several, or two living villagers with the same cut name
and looks, decide nothing and are reported.

Check Saves & Logs reports what it finds; Repair Saves & Logs restores the full names in the save and
in every log record carrying the cut name (restore), through Last Names' renaming
(vv_last_names.plan_renames / apply) with its safety: the game must be closed, the save folder is
backed up first ("(before restoring cut names)"), every file is swapped in and read back, and any
failure puts every changed file back.  The Family Tree Maker and the Village Matchmaker show the
full name (vv_genealogy.load_village).
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import vv_last_names as ln
import vv_save_backup

BACKUP_LABEL = "(before restoring cut names)"

# How many characters each game's Villager Details screen keeps of a name when it closes (measured
# live 2026-10-07); a very wide name keeps fewer.
DETAILS_ROOM = {1: 10, 2: 18, 3: 18, 4: 18, 5: 18}
# How much shorter wide letters leave a cut name (measured live: 9 'M's in A New Home, 15 in the others).
WIDE_SLACK = {1: 1, 2: 3, 3: 3, 4: 3, 5: 3}

# The records that say a villager is no longer in the village.
GONE_HEADINGS = ("Death", "Disappeared", "Left", "Unaccounted")


@dataclass
class Cut:
    """A living villager whose name the Villager Details screen cut, and the full name the logs keep."""
    villager: ln.Living
    full: str

    @property
    def renames(self) -> dict[tuple, str]:
        return {self.villager.identity: self.full}


def _words(blocks, identity: tuple) -> set[tuple[str, str]]:
    """The (likes, dislikes) the logs record for `identity`."""
    out = set()
    for b in blocks:
        if b.identity == identity:
            likes, dislikes = b.value("Likes"), b.value("Dislikes")
            if likes is not None and dislikes is not None:
                out.add((likes, dislikes))
    return out


def find_cut(folder: Path, game: int, slot: int) -> tuple[list[Cut], list[str]]:
    """Every living villager whose name the Villager Details screen cut, with the full name the logs
    keep, and notes on the names that cannot be decided.  Reads only."""
    import vv_log_additions as additions
    folder = Path(folder)
    if additions.current_villages(folder, game, slot) is None:
        # The records of an erased village could not be told from this one's (as Number Duplicate Names).
        return [], ["The save's tribe name could not be read, so no cut-off name is matched to the logs."]
    room, fits = DETAILS_ROOM[game], ln.ROOM[game]
    people = ln.living(folder, game, slot)
    blocks = additions.person_blocks(folder, slot, game)
    living_names = {v.name for v in people}
    gone = {b.identity for b in blocks if b.heading.startswith(GONE_HEADINGS)}
    sexes: dict[tuple, set[str]] = {}
    for b in blocks:
        sex = b.value("Sex")
        if sex in ("Male", "Female"):
            sexes.setdefault(b.identity, set()).add(sex)
    logged = {b.identity for b in blocks if b.identity[0] and b.identity[1] is not None and b.identity[2] is not None}
    same: dict[tuple, int] = {}
    for v in people:
        same[v.identity] = same.get(v.identity, 0) + 1
    cuts: list[Cut] = []
    notes: list[str] = []
    for v in people:
        # Only what the screen does to a name: the cut keeps `room` characters, or a few fewer when
        # the letters are wide (measured live: 9 'M's in A New Home, 15 in the others), and the full
        # name was longer than the box -- so a name the player shortened on purpose ("Chapa
        # Wanjiko" -> "Chapa") is never "restored" (review, 2026-10-07).
        if not v.name or not room - WIDE_SLACK[game] <= len(v.name) <= room:
            continue
        found = sorted({name for name, head, body in logged
                        if (head, body) == (v.head, v.body) and len(name) > room and name.startswith(v.name)
                        and len(name) <= fits and all(0x20 <= ord(ch) < 0x7F for ch in name)
                        and (name, head, body) not in gone and name not in living_names
                        and sexes.get((name, head, body), {v.sex}) == {v.sex}
                        and _likes_agree(blocks, v.identity, (name, head, body))})
        if not found:
            continue
        if same[v.identity] > 1:
            note = (f"{same[v.identity]} living villagers are called {v.name} with head {v.head} and body {v.body}, "
                    f"so which of them is {' or '.join(found)} cannot be told; their names are left as they are.")
            if note not in notes:
                notes.append(note)
            continue
        if len(found) > 1:
            notes.append(f"{v.name} (head {v.head}, body {v.body}) could be {' or '.join(found)}; "
                         "the name is left as it is.")
            continue
        cuts.append(Cut(v, found[0]))
    return cuts, notes


def _likes_agree(blocks, cut: tuple, full: tuple) -> bool:
    """The likes and dislikes the logs record under the cut name and under the full one agree --
    or one of them has none to compare."""
    under_cut, under_full = _words(blocks, cut), _words(blocks, full)
    return not under_cut or not under_full or bool(under_cut & under_full)


def describe(cuts: list[Cut], pair: str = "{cut} -> {full}", limit: int = 12) -> str:
    """"Hoani Gued -> Hoani Guedado, ..." (each as `pair`; at most `limit`, then how many more)."""
    text = ", ".join(pair.format(cut=c.villager.name, full=c.full) for c in cuts[:limit])
    return text + (f" and {len(cuts) - limit} more" if len(cuts) > limit else "")


def plan(folder: Path, game: int, slot: int) -> ln.Plan:
    """What restoring the full names changes, file by file: the save, and every record carrying a cut
    name (the living only; nobody is asked about look-alikes -- each cut name is one name, head and
    body).  Reads only."""
    cuts, notes = find_cut(folder, game, slot)
    renames: dict[tuple, str] = {}
    for cut in cuts:
        renames.update(cut.renames)
    work = ln.plan_renames(folder, game, slot, renames, dead=False, ask=False)
    work.notes[:0] = notes
    return work


def restore(folder: Path, game: int, slot: int, processes: vv_save_backup.ProcessController | None = None,
            now: datetime | None = None) -> ln.Result:
    """Give every cut name back its full name, in the save and every log.  Refused (nothing changed)
    while the game runs or when no cut name is found; the save folder is backed up first; any
    failure puts every changed file back."""
    folder = Path(folder)
    controller = processes if processes is not None else vv_save_backup.WindowsProcesses()
    ln.tools._refuse_if_running(folder, controller)
    try:
        work = plan(folder, game, slot)
    except (struct.error, ValueError, OSError) as exc:
        raise ln.LastNamesError(f"A file could not be read ({exc}); nothing was changed.") from exc
    if not work.renames:
        raise ln.LastNamesError(" ".join(work.notes) or "No name the Villager Details screen cut short was found.")
    return ln.apply(folder, work, controller, now, BACKUP_LABEL, "restoring the cut names")
