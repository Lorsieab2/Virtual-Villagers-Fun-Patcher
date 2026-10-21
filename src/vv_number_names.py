"""Number Duplicate Names: villagers who share a name, numbered in the game and in the logs (all five games).

The owner (2026-10-07): "How about a "Number duplicate names" button in the family tree maker and repair
logs?  If there are duplicate "Soda"s, name the first one "Soda I", and the second one "Soda II" etc.
Also offer to edit the save files."

Everyone the save and the logs know is numbered, the dead too, in order of appearance unless the player
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
import vv_save_layout as layout

BACKUP_LABEL = "(before numbering names)"


class NothingToNumber(ln.LastNamesError):
    """Nothing was renamed, which is no error: no name is shared, or every one left is the player's to
    decide (`notes`, shown as information, never as a failure; the owner, 2026-10-20)."""

    def __init__(self, notes: list[str]):
        self.notes = list(notes)
        super().__init__(" ".join(self.notes) or "No two villagers share a name.")


@dataclass
class Numbering:
    renames: dict[tuple, str] = field(default_factory=dict)    # (name, head, body) -> numbered name
    notes: list[str] = field(default_factory=list)              # who is left as they are, and why
    # NAMESAKES WITH THE SAME LOOKS (the owner, 2026-10-20: "fix this too!!!" -- villagers of the same
    # name, head and body were left unnumbered with a red error).  (name, head, body) -> the numbered
    # names, one for each holder in
    # the save, the OLDEST first (the owner's oldest-first rule); villagers of the same age as well
    # (identical twins) in the order the game keeps them (the save's record order, the Births log's
    # order of the delivery).  vv_last_names.plan_renames(ordered=...) ties each record to one of them.
    ordered: dict[tuple, list[str]] = field(default_factory=dict)
    # What renaming them did: (name, head, body, age) -> new name, one for each villager renamed.
    numbered: list[tuple[tuple, str]] = field(default_factory=list)


def orderable(folder: Path, game: int, slot: int, alike: dict[tuple, int]) -> set[tuple]:
    """The look-alike (name, head, body) whose every holder is a villager in the save (living or a
    body there): those can be told apart by age and by the game's own order, and are numbered.  One
    also named by a Death or Disappeared record -- a holder the save no longer holds -- is not."""
    held = Counter(v.identity for v in ln.living(folder, game, slot, bodies=True))
    return {key for key, count in alike.items() if held.get(key, 0) == count}


def numbering(village: gen.Village, alike: dict[tuple, int] | None = None,
              nameless: set[str] = frozenset(), bodies: set[tuple] = frozenset(),
              taken: set[str] = frozenset(), order: str = "appearance",
              orderable: set[tuple] = frozenset()) -> Numbering:
    """The numbered name of each villager the save and the logs can tell apart.  `alike`: each
    (name, head, body) the save holds more than once, and how many times; `nameless`: the names of
    records that do not say how their villager looks; `bodies`: the (name, head, body) of the dead
    lying in the save; `taken`: names the patcher's own files hold (never given again);
    `orderable`: the `alike` ones whose holders are all in the save (orderable()): numbered each, in
    Numbering.ordered."""
    out = Numbering()
    alike = alike or {}
    for (name, _head, _body), count in sorted(alike.items()):
        if (name, _head, _body) in orderable:
            continue
        out.notes.append(f"{count} villagers are called {name} and look the same (head {_head}, body {_body}), "
                         "and not all of them are in the save (a Death or Disappeared record names one), so "
                         "the records cannot tell which is which: they keep their name.")
    # A namesake known only from records -- neither in the save nor recorded as dead or gone -- may be
    # a living namesake before Change Appearance (Codex, #557): that record keeps its name and is not
    # counted, so the villagers the save holds are numbered among themselves.
    living_names = {p.name for p in village.known() if p.alive}
    unsure = {p.id for p in village.known() if p.name in living_names and not p.alive and not p.gone
              and p.head is not None and p.body is not None and p.key not in bodies}
    # A record left under the old name when namesakes of the same looks were numbered one by one (one that
    # could not be tied to which of them, Plan.untied) is one of them, not another villager: it is neither
    # numbered nor counted, so a second Repair changes nothing.
    numbered_looks = {(gen.unnumbered(p.name), p.head, p.body) for p in village.known()
                      if p.alive and gen.unnumbered(p.name) != p.name}
    unsure |= {p.id for p in village.known() if not p.alive and not p.gone and p.key not in bodies
               and p.key in numbered_looks}
    # A record that does not say how its villager looks is never numbered and never counted among the
    # namesakes -- only its name is taken (the owner, 2026-10-20: a Repair audit found every Repair
    # renaming Gata Sirikit II to III and back, because such a record took a number each time).
    lookless = {p.id for p in village.known() if p.head is None or p.body is None}
    weight = {p.id: alike[p.key] for p in village.known() if p.key in alike}
    blocks: dict[int, list[str]] = {}
    numbered = gen.duplicate_names(village, order,
                                   reserved=set(nameless) | set(taken) | {village.people[q].name for q in lookless},
                                   leave=unsure | lookless, weight=weight, blocks=blocks)
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
            names = blocks.get(pid, [])
            if (name, head, body) not in orderable or len(names) != alike[(name, head, body)]:
                continue
            if any(len(n) > ln.ROOM[village.game] for n in names):
                out.notes.append(f"{names[-1]} is longer than the game's {ln.ROOM[village.game]} characters, so "
                                 f"the {len(names)} villagers called {name} keep their name.")
            else:
                out.ordered[(name, head, body)] = names
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
    for path, columns in ((layout.route(folder, f"{layout.DATA}\\Village Statistics\\Villagers Counted - Save {slot}.dat"),
                           (1,)),
                          (layout.route(folder, f"{layout.DATA}\\Village Elders\\Village Elders - Save {slot}.dat"),
                           (2, 3, 4))):
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


def number_names(folder: Path, game: int, slot: int, order: str = "appearance",
                 processes: vv_save_backup.ProcessController | None = None,
                 now: datetime | None = None, automatic: bool = False) -> tuple[ln.Result, Numbering]:
    """Number every duplicate name in the save, the logs and the patcher's files.  Refused (nothing
    changed) while the game runs or when no name is shared.  One "Repair <n>" record in the Repairs
    Made log lists every rename and what was left as it was (`automatic`: the village's setting did it)."""
    folder = Path(folder)
    controller = processes if processes is not None else vv_save_backup.WindowsProcesses()
    ln.tools._refuse_if_running(folder, controller)
    import vv_log_additions as additions
    if additions.current_villages(folder, game, slot) is None:   # records of an erased village (Codex, #557)
        raise ln.LastNamesError("The save's tribe name could not be read, so this village's records cannot be "
                                "told from an earlier village's; nothing was changed.")
    try:
        wanted = pending(folder, game, slot, order)
        try:
            work = ln.plan_renames(folder, game, slot, wanted.renames, dead=True, ordered=wanted.ordered)
        except ln.LastNamesError as exc:
            if not wanted.ordered:
                raise
            # Namesakes with the same looks the patcher's titles or masks cannot tell apart (vv_last_names
            # refuses rather than guesses): they keep their names, and everyone else is numbered.
            wanted.notes.append(f"The villagers called {', '.join(sorted({k[0] for k in wanted.ordered}))} "
                                f"keep their names: {exc}")
            wanted.ordered = {}
            work = ln.plan_renames(folder, game, slot, wanted.renames, dead=True)
        wanted.notes += work.notes
        wanted.numbered = list(work.numbered)
    except (gen.GenealogyError, struct.error, ValueError, OSError) as exc:
        raise ln.LastNamesError(f"A file could not be read ({exc}); nothing was changed.") from exc
    if not work.renames and not work.numbered:
        # Not an error (the owner, 2026-10-20): nothing to number, or only what is left for the player.
        raise NothingToNumber(wanted.notes)
    result = ln.apply(folder, work, controller, now, BACKUP_LABEL, "numbering the names")
    try:
        note_numbering(folder, game, slot, result, wanted, now, automatic)
    except OSError:
        pass                                    # the renames stand; the save and the logs show them
    return result, wanted


# NUMBERED AUTOMATICALLY (the owner, 2026-10-20: numbering villagers who share a full name "must be ON BY
# DEFAULT" -- done without the player pressing the button, in the game and in every log, as a per-village
# setting).  Kept in the save's own Data folder:
#     <save folder>\Virtual Villagers Fun Patcher\Save <slot>\Data\Number Names\
#         Virtual Villagers <game> Number Names - Save <slot>.dat
# a "VVFP NUMBER NAMES v1 game=<game>" line, then "auto<TAB>on" or "auto<TAB>off".  No file, or no such
# line, is ON.  Repair Saves & Logs keeps the choice ("Number villagers who share a name automatically");
# with it on, every Repair numbers what Number Duplicate Names would (backup first, a Repairs Made record),
# and "VVFP Number Names.dll" numbers a baby born with a living villager's full name at its birth.
SETTING_HEADER = "VVFP NUMBER NAMES v1 game={game}"
AUTO_ON, AUTO_OFF = "on", "off"


def setting_path(folder: Path, game: int, slot: int) -> Path:
    return layout.route(Path(folder), f"{layout.DATA}\\Number Names\\"
                                      f"Virtual Villagers {game} Number Names - Save {slot}.dat")


def read_auto(folder: Path, game: int, slot: int) -> bool:
    """The village's setting: True (on) unless its file says "auto<TAB>off"."""
    try:
        lines = setting_path(folder, game, slot).read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return True
    if not lines or lines[0] != SETTING_HEADER.format(game=game):
        return True
    for line in lines[1:]:
        parts = line.split("\t")
        if parts[0] == "auto" and len(parts) == 2 and parts[1] in (AUTO_ON, AUTO_OFF):
            return parts[1] == AUTO_ON
    return True


def save_auto(folder: Path, game: int, slot: int, on: bool,
              processes: vv_save_backup.ProcessController | None = None) -> bool:
    """Keep the village's setting (refused while the game runs: the companion reads it at each birth).
    True when it changed."""
    controller = processes if processes is not None else vv_save_backup.WindowsProcesses()
    ln.tools._refuse_if_running(Path(folder), controller)
    if on == read_auto(folder, game, slot):
        return False
    path = setting_path(folder, game, slot)
    path.parent.mkdir(parents=True, exist_ok=True)
    ln._write(path, (SETTING_HEADER.format(game=game) + f"\nauto\t{AUTO_ON if on else AUTO_OFF}\n").encode("utf-8"))
    return True


def pending(folder: Path, game: int, slot: int, order: str = "appearance") -> Numbering:
    """What numbering would do now (read only): the renames, and the notes on who would be left as they
    are and why -- the cases the player decides, never guessed."""
    found = evidence(folder, game, slot)
    return numbering(gen.load_village(folder, game, slot, full_names=False), *found, order=order,
                     orderable=orderable(folder, game, slot, found[0]))


def _village_header(folder: Path, game: int, slot: int) -> str | None:
    import vv_tribe_rename
    try:
        named = {g.number: g for g in vv_tribe_rename.GAMES}[game]
        name = vv_tribe_rename.save_name(named, ln.save_path(folder, game, slot).read_bytes())
    except (KeyError, ValueError, struct.error, OSError):
        return None
    return vv_tribe_rename.village_header(name, slot) if name else None


def wanted_names(wanted: Numbering) -> dict[tuple, str]:
    """Every rename a numbering would make, for showing: (name, head, body) -> the new name, or for
    namesakes with the same looks numbered one by one, their new names oldest first ("Goby Kalama I /
    Goby Kalama II")."""
    out = dict(wanted.renames)
    out.update({key: " / ".join(names) for key, names in wanted.ordered.items()})
    return out


def renamed_count(result: ln.Result, wanted: Numbering) -> int:
    """How many villagers a numbering renamed: by name, head and body, and one by one."""
    return len(result.renamed) + len(wanted.numbered)


def note_numbering(folder: Path, game: int, slot: int, result: ln.Result, wanted: Numbering,
                   now: datetime | None = None, automatic: bool = False) -> None:
    """One "Repair <n>" record in the Repairs Made log (native/shared/repairs_log.h's shape, numbered as
    src/vv_log_tools.py repair_record_start numbers it): every villager renamed, old -> new, and every
    villager left as they were and why."""
    folder = Path(folder)
    header = _village_header(folder, game, slot) or "Village: (all villages in this save folder)"
    path, text = ln.tools.repair_record_start(folder, game, header, layout.header_slot(header) or slot, now)
    text += ("  Checked: villagers who share a full name, numbered oldest first (Number villagers who share a "
             "name automatically)\r\n" if automatic else
             "  Checked: villagers who share a full name (Number Duplicate Names)\r\n")
    for (old, head, body), new in sorted(result.renamed.items(), key=lambda item: (item[1], item[0])):
        text += f"  Renamed: {old} (head {head}, body {body}) -> {new}\r\n"
    for (old, head, body, age), new in wanted.numbered:
        text += (f"  Renamed: {old} (head {head}, body {body}" + (f", age {age}" if age is not None else "")
                 + f") -> {new}\r\n")
    for note in wanted.notes:
        text += f"  Left as it was: {note}\r\n"
    text += f"  Files changed: {len(result.files)}\r\n"
    text += f"  Backup: {Path(result.backup.backup_folder).name}\r\n\r\n"
    with open(path, "ab") as log:
        log.write(text.encode("latin-1", "replace"))
