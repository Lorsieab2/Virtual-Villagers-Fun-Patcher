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
    # Each look-alike key takes its numbers once, as one block (Numbering.ordered): on the first of its villagers.
    # The family tree reads two living namesakes as two villagers (vv_genealogy, v1.35.85); the others of the key
    # are in that block already, so they are left out of the count rather than numbered again.
    weight: dict[int, int] = {}
    in_block: set[int] = set()
    for p in sorted(village.known(), key=lambda q: q.id):
        if p.key not in alike:
            continue
        if p.key in {village.people[q].key for q in weight}:
            in_block.add(p.id)
        else:
            weight[p.id] = alike[p.key]
    blocks: dict[int, list[str]] = {}
    numbered = gen.duplicate_names(village, order,
                                   reserved=set(nameless) | set(taken) | {village.people[q].name for q in lookless},
                                   leave=unsure | lookless | in_block, weight=weight, blocks=blocks)
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
    for pid, names in sorted(blocks.items(), key=lambda item: item[1]):
        key = village.people[pid].key
        if key not in alike or key not in orderable or len(names) != alike[key]:
            continue
        if any(len(n) > ln.ROOM[village.game] for n in names):
            out.notes.append(f"{names[-1]} is longer than the game's {ln.ROOM[village.game]} characters, so "
                             f"the {len(names)} villagers called {key[0]} keep their name.")
        else:
            out.ordered[key] = names
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
        _record_used_quietly(folder, game, slot, controller)
        # Not an error (the owner, 2026-10-20): nothing to number, or only what is left for the player.
        raise NothingToNumber(wanted.notes)
    result = ln.apply(folder, work, controller, now, BACKUP_LABEL, "numbering the names")
    try:
        note_numbering(folder, game, slot, result, wanted, now, automatic)
    except OSError:
        pass                                    # the renames stand; the save and the logs show them
    _record_used_quietly(folder, game, slot, controller)
    return result, wanted


def _record_used_quietly(folder: Path, game: int, slot: int, controller) -> None:
    """record_used, where a failure changes nothing else (the next Repair keeps them again)."""
    try:
        record_used(folder, game, slot, controller)
    except (ln.LastNamesError, gen.GenealogyError, struct.error, ValueError, OSError):
        pass


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


def _write_setting(folder: Path, game: int, slot: int, on: bool, used: dict[str, set[int]]) -> None:
    path = setting_path(folder, game, slot)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [SETTING_HEADER.format(game=game), f"auto\t{AUTO_ON if on else AUTO_OFF}"]
    lines += [f"used\t{base}\t{n}" for base in sorted(used) for n in sorted(used[base])]
    ln._write(path, ("\n".join(lines) + "\n").encode("utf-8"))


def save_auto(folder: Path, game: int, slot: int, on: bool,
              processes: vv_save_backup.ProcessController | None = None) -> bool:
    """Keep the village's setting (refused while the game runs: the companion reads it at each birth).
    True when it changed.  The numbers already used (read_used) are kept with it."""
    controller = processes if processes is not None else vv_save_backup.WindowsProcesses()
    ln.tools._refuse_if_running(Path(folder), controller)
    if on == read_auto(folder, game, slot):
        return False
    _write_setting(folder, game, slot, on, read_used(folder, game, slot))
    return True


# NUMBERS ARE NEVER GIVEN TWICE (the owner, 2026-10-20): "a new namesake gets the next free number after the
# highest ever used for that name (including dead/gone holders in the logs)".  The same file keeps every
# number used for each name, a line "used<TAB><name without its number><TAB><n>" (the name in UTF-8):
# the patcher writes the numbers the save and the logs know (record_used), and VVFP Number Names.dll adds
# each one it gives at a birth -- so the companion, which sees only the living, never gives a number a dead
# or gone villager had, and the patcher never gives one the companion gave.
def read_used(folder: Path, game: int, slot: int) -> dict[str, set[int]]:
    try:
        lines = setting_path(folder, game, slot).read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return {}
    if not lines or lines[0] != SETTING_HEADER.format(game=game):
        return {}
    out: dict[str, set[int]] = {}
    for line in lines[1:]:
        parts = line.split("\t")
        if parts[0] == "used" and len(parts) == 3 and parts[1] and parts[2].isdigit() and 0 < int(parts[2]) < 4000:
            out.setdefault(parts[1], set()).add(int(parts[2]))
    return out


def _known_numbers(folder: Path, game: int, slot: int) -> dict[str, set[int]]:
    """Every number the save, the logs and the patcher's files show in use, by the name it numbers."""
    out: dict[str, set[int]] = {}
    village = gen.load_village(folder, game, slot, full_names=False)
    _alike, nameless, _bodies, taken = evidence(folder, game, slot)
    for name in [p.name for p in village.known()] + sorted(nameless) + sorted(taken):
        base, value = gen.unnumbered(name), gen.roman_value(name.rsplit(" ", 1)[-1])
        if base != name and value:
            out.setdefault(base, set()).add(value)
    return out


def record_used(folder: Path, game: int, slot: int,
                processes: vv_save_backup.ProcessController | None = None) -> bool:
    """Keep in the village's file every number now in use (with those it already keeps); refused while the
    game runs.  True when the file changed."""
    controller = processes if processes is not None else vv_save_backup.WindowsProcesses()
    ln.tools._refuse_if_running(Path(folder), controller)
    used = read_used(folder, game, slot)
    merged = {base: set(ns) for base, ns in used.items()}
    for base, ns in _known_numbers(folder, game, slot).items():
        merged.setdefault(base, set()).update(ns)
    if merged == used:
        return False
    _write_setting(folder, game, slot, read_auto(folder, game, slot), merged)
    return True


def pending(folder: Path, game: int, slot: int, order: str = "appearance") -> Numbering:
    """What numbering would do now (read only): the renames, and the notes on who would be left as they
    are and why -- the cases the player decides, never guessed."""
    alike, nameless, bodies, taken = evidence(folder, game, slot)
    taken = set(taken) | {f"{base} {gen.roman(n)}" for base, ns in read_used(folder, game, slot).items() for n in ns}
    return numbering(gen.load_village(folder, game, slot, full_names=False), alike, nameless, bodies, taken,
                     order=order, orderable=orderable(folder, game, slot, alike))


# A NUMBER A LOOKS OR TITLE CHANGE GAVE (the owner, v1.35.80 update: "A change in body, head and mask does not
# mean they disappeared.  A change in title or special villager status does not mean they disappeared.").
# Before this update the Family Tree reader took a villager's record under older looks -- The Secret City's
# new Tribal Chief in the chief's robe, an island event's new head -- for a second villager of the same name,
# and numbering (the automatic numbering at every Repair included) then numbered the villager as that
# "namesake's" successor.  Such a number was never legitimately given, so -- unlike every real number, which
# is kept for life (numbered-names-keep-their-number) -- Repair Saves & Logs offers to take it off again,
# villager by villager, with the evidence, only when the villager has no other holder of the name at all
# (living, dead, gone or in any record) once their older looks are known to be theirs.
UNNUMBER_KIND = "looks_numbers"
UNNUMBER_LABEL = "Numbers given because a villager's looks or title changed"
TAKE_OFF = "Take the number off"
KEEP_NUMBER = "Keep the number"


@dataclass
class Misnumbered:
    """A living villager whose number only a change of their own looks or title explains."""
    name: str                       # as the save has it now ("Mama Peponi II")
    base: str                       # without the number ("Mama Peponi")
    head: int
    body: int
    age: int | None
    older_looks: list[tuple[int, int]]          # the looks the older records give them
    renamed_lines: list[str] = field(default_factory=list)   # the Repairs Made lines that numbered them

    @property
    def key(self) -> str:
        return f"unnumber|{self.name}|{self.head}|{self.body}"

    def evidence(self) -> str:
        looks = "; ".join(f"head {h}, body {b}" for h, b in self.older_looks)
        made = (" " + " ".join(self.renamed_lines)) if self.renamed_lines else ""
        return (f"{self.name} (head {self.head}, body {self.body}{', age ' + str(self.age) if self.age is not None else ''}) "
                f"has no other villager called {self.base} -- living, dead, gone or in any record. The only other "
                f"\"{self.base}\" the records name is this villager under their older looks ({looks}), before a "
                f"change of looks or title (The Secret City's Tribal Chief's robe, an island event, Change Appearance), "
                f"which never means a villager left.{made}")


def _numbering_lines(folder: Path, game: int, slot: int) -> list[str]:
    """Every "Renamed: <old> (head h, body b...) -> <new>" line in the slot's Repairs Made logs."""
    out = []
    checker = ln.tools.load_checker()
    for path in checker.game_logs(Path(folder), layout.REPAIRS_LOGS, f"Virtual Villagers {game} Repairs Log"):
        try:
            text = path.read_bytes().decode("latin-1")
        except OSError:
            continue
        out += [line.strip() for line in text.splitlines() if line.strip().startswith("Renamed: ")]
    return out


def misnumbered_by_looks(folder: Path, game: int, slot: int,
                         village: gen.Village | None = None) -> list[Misnumbered]:
    """The living villagers numbered only because a change of their own looks or title split them in two
    (read only): a number in their name, no other holder of the name once their older looks are joined to
    them, and an older record of the name without the number, under other looks, that is theirs."""
    folder = Path(folder)
    village = village if village is not None else gen.load_village(folder, game, slot, full_names=False)
    _alike, nameless, _bodies, _taken = evidence(folder, game, slot)
    lines = _numbering_lines(folder, game, slot)
    out = []
    for p in village.living():
        base = gen.unnumbered(p.name)
        if base == p.name or not gen.roman_value(p.name.rsplit(" ", 1)[-1]) or p.head is None or p.body is None:
            continue
        if any(q.id != p.id and gen.unnumbered(q.name) == base for q in village.known()):
            continue                            # a real namesake: the number stays, for life
        if any(gen.unnumbered(n) == base for n in nameless):
            continue                            # a record without looks may be another of the name
        older = [(h, b) for (name, h, b), now in village.relooked.items()
                 if now == p.key and name == base and (h, b) != (p.head, p.body)]
        if not older:
            continue                            # nothing says a looks change made the number
        made = [line for line in lines if line.startswith(f"Renamed: {base} (") and line.endswith(f"-> {p.name}")]
        out.append(Misnumbered(p.name, base, p.head, p.body, p.age, sorted(set(older)), made))
    return out


def take_numbers_off(folder: Path, game: int, slot: int, cases: list[Misnumbered],
                     processes: vv_save_backup.ProcessController | None = None,
                     now: datetime | None = None) -> ln.Result | None:
    """Take off the numbers a looks or title change gave (the player answered "Take the number off"):
    the save, the logs and the patcher's files renamed back (vv_last_names' renaming: refused while the game
    runs, the save folder backed up first, every file read back, every one put back on a failure); the
    number taken out of the village's used numbers (it was never given); one Repairs Made record listing each
    with its evidence.  Each case is checked again first: one that no longer holds is left as it is."""
    folder = Path(folder)
    controller = processes if processes is not None else vv_save_backup.WindowsProcesses()
    ln.tools._refuse_if_running(folder, controller)
    still = {c.key: c for c in misnumbered_by_looks(folder, game, slot)}
    todo = [still[c.key] for c in cases if c.key in still]
    if not todo:
        return None
    work = ln.plan_renames(folder, game, slot, {(c.name, c.head, c.body): c.base for c in todo}, dead=True)
    if not work.changes:
        return None
    result = ln.apply(folder, work, controller, now, "(before taking off numbers)",
                      "taking off the numbers a looks change gave")
    used = read_used(folder, game, slot)
    changed = False
    for c in todo:
        value = gen.roman_value(c.name.rsplit(" ", 1)[-1])
        if value in used.get(c.base, set()):
            used[c.base].discard(value)
            changed = True
    if changed:
        try:
            _write_setting(folder, game, slot, read_auto(folder, game, slot),
                           {b: ns for b, ns in used.items() if ns})
        except OSError:
            pass                                # the names are right; the next Repair writes the file again
    try:
        header = _village_header(folder, game, slot) or "Village: (all villages in this save folder)"
        path, text = ln.tools.repair_record_start(folder, game, header, layout.header_slot(header) or slot, now)
        text += ("  Checked: villagers numbered only because their own looks or title changed (an owner-approved "
                 "correction: the number was never legitimately given)\r\n")
        for c in todo:
            text += f"  Number taken off: {c.name} (head {c.head}, body {c.body}) -> {c.base}\r\n"
            text += f"    Evidence: {c.evidence()}\r\n"
        text += f"  Files changed: {len(result.files)}\r\n"
        text += f"  Backup: {Path(result.backup.backup_folder).name}\r\n\r\n"
        with open(path, "ab") as log:
            log.write(text.encode("latin-1", "replace"))
    except OSError:
        pass                                    # the renames stand; the save and the logs show them
    return result


def plan_unnumber(folder: Path, game: int, slot: int):
    """Repair Saves & Logs' row for the numbers a looks or title change gave: one question per villager, with
    the evidence (never ticked or answered for the player: "Keep the number" is where each starts)."""
    import vv_log_additions as additions
    kind = additions.Kind(UNNUMBER_KIND, UNNUMBER_LABEL)
    try:
        cases = misnumbered_by_looks(folder, game, slot)
    except (gen.GenealogyError, ln.LastNamesError, struct.error, ValueError, OSError) as exc:
        kind.notes.append(f"Numbers given by a looks change were not checked: a file could not be read ({exc}).")
        return kind
    for c in cases:
        kind.questions[c.key] = additions.Question(
            c.key, f"{c.evidence()} Take the number off ({c.name} -> {c.base})?",
            [TAKE_OFF, KEEP_NUMBER, additions.DONT_KNOW], KEEP_NUMBER, "number-from-looks",
            ((c.name, c.head, c.body),))
    kind.context["cases"] = {c.key: c for c in cases}
    kind.context["game"], kind.context["slot"] = game, slot
    return kind


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
