"""Restore A New Home's parents from the copies the patcher kept of its parentage file.

A New Home keeps no parents in its save: "VVFP VV1 Parentage.dll" keeps them in
"Virtual Villagers 1 Parentage Records - Save <n>.dat" (native/vv1_parentage/vv1_parentage.c:
a 12-byte 'VP02' header, 256 roster occupants of 36 bytes, 256 entries of 92 bytes).  v1.35.66 and
v1.35.67 could write an empty table over that file (the title screen's seeded founders, fixed in
v1.35.68), and the Births log can give back only the parents of villagers whose Birth record still
matches their name and looks: a villager whose looks changed since birth (an island event, Change
Appearance) and the dead have their parents only in the file.

Every copy the patcher made of the file -- before each repair ("<name>.before-...", beside it or in
"Copies Made Before Repairs"), a file set aside ("<name>.unreadable-...", "<name>.another-village-...")
-- is read, newest first, and for each villager the file now names with NO parents at all, the newest
copy that names parents for that villager (gender, family number and name, the companion's own
identity) gives them back.  It only ever adds:

  - an entry that has any parent now is never changed (a newer real change wins);
  - a pregnancy's expected father is never touched;
  - a villager the file no longer names (dead and dropped by an older build) comes back as a departed
    entry in a free record, so the logs and the family tree keep their parents;
  - two villagers who share the identity in the file or in a copy are left alone, never guessed;
  - a copy whose parents disagree with the villager's own Birth record (same name and looks) is not
    used for them: that is a contradiction the player decides (Check Saves & Logs lists it).

Refused while the game runs.  The save folder is backed up first, the file is copied into Copies Made
Before Repairs, and a Repair record goes into the Repairs Made log."""
from __future__ import annotations

import os
import re
import struct
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import vv_log_tools as tools
import vv_save_backup
import vv_save_layout as layout

MAGIC = b"VP02"
HEADER = 12
OCCUPANT = 36
ENTRY = 92
COUNT = 256
SIZE = HEADER + COUNT * OCCUPANT + COUNT * ENTRY
NAME = 28
COPY_SUFFIX = ".before-parents-restore"


class RestoreError(Exception):
    pass


def file_name(slot: int) -> str:
    return f"Virtual Villagers 1 Parentage Records - Save {slot}.dat"


def parents_path(folder: Path, slot: int) -> Path:
    """The file the companion reads and writes (native vv1_parents_path): "Parents (A New Home)" or
    an older build's "Parentage Records", whichever holds it; else the loose name in the Data folder."""
    folder = Path(folder)
    found = layout.find(folder, f"{layout.DATA}\\{layout.PARENTS_VV1}\\{file_name(slot)}")
    if found.is_file():
        return found
    loose = folder / layout.DATA / file_name(slot)
    return loose if loose.is_file() else found


def _cstr(buf: bytes, at: int) -> str:
    return bytes(buf[at:at + NAME]).split(b"\0", 1)[0].decode("latin-1")


@dataclass
class Table:
    data: bytearray

    def occupant(self, i: int) -> tuple[int, int, int, int, int, str]:
        o = HEADER + i * OCCUPANT
        d = self.data
        return d[o], d[o + 1], d[o + 2], d[o + 3], struct.unpack_from("<i", d, o + 4)[0], _cstr(d, o + 8)

    def identity(self, i: int) -> tuple[str, int, int] | None:
        gender, _dep, _h, _b, scalar, name = self.occupant(i)
        return (name, gender, scalar) if gender in (1, 2) else None

    def entry_at(self, i: int) -> int:
        return HEADER + COUNT * OCCUPANT + i * ENTRY

    def parents(self, i: int) -> bytes:
        """The father and mother: looks bytes 0..3 and the two names; never the stash."""
        e = self.entry_at(i)
        return bytes(self.data[e:e + 4]) + bytes(self.data[e + 8:e + 8 + 2 * NAME])

    def has_parents(self, i: int) -> bool:
        return any(self.parents(i))

    def names(self, i: int) -> tuple[str, str]:
        e = self.entry_at(i)
        return _cstr(self.data, e + 8), _cstr(self.data, e + 8 + NAME)

    def looks(self, i: int) -> tuple[int, int]:
        _g, _d, h, b, _s, _n = self.occupant(i)
        return h - 1, b - 1                                # stored + 1; 0 (-1 here) = not recorded

    def put_parents(self, i: int, parents: bytes) -> None:
        e = self.entry_at(i)
        self.data[e:e + 4] = parents[:4]
        self.data[e + 8:e + 8 + 2 * NAME] = parents[4:]

    def empty_record(self, i: int) -> bool:
        e = self.entry_at(i)
        o = HEADER + i * OCCUPANT
        return not any(self.data[o:o + OCCUPANT]) and not any(self.data[e:e + ENTRY])


def read_table(path: Path, slot: int) -> Table | None:
    try:
        data = Path(path).read_bytes()
    except OSError:
        return None
    if len(data) != SIZE or data[:4] != MAGIC or struct.unpack_from("<I", data, 8)[0] != slot:
        return None
    return Table(bytearray(data))


def copies(folder: Path, slot: int) -> list[Path]:
    """Every copy of the slot's file the patcher made, newest first."""
    folder = Path(folder)
    stem = file_name(slot) + "."
    out = []
    data = folder / layout.DATA
    if data.is_dir():
        for path in data.rglob(file_name(slot) + ".*"):
            if path.is_file() and path.name.startswith(stem) and not path.name.endswith(".tmp"):
                out.append(path)
    out.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return out


@dataclass
class Restored:
    name: str
    father: str
    mother: str
    source: str
    departed: bool = False


@dataclass
class Plan:
    path: Path
    original: bytes
    table: Table
    restored: list[Restored] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    ambiguous: list[str] = field(default_factory=list)

    def lines(self) -> list[str]:
        out = []
        for r in self.restored:
            what = "a departed villager's parents kept" if r.departed else "parents restored"
            out.append(f"{r.name}: {what} -- father {r.father or '(unknown)'}, mother {r.mother or '(unknown)'} "
                       f"(from {r.source})")
        out += [f"Not restored (the copy and the Births log disagree; Check Saves & Logs asks): {c}"
                for c in self.conflicts]
        out += [f"Not restored (two villagers share the name, family and gender): {a}" for a in self.ambiguous]
        return out


def _births_log_parents(folder: Path, slot: int) -> dict[tuple[str, int, int], set[tuple[str, str]]]:
    """(child name, head, body) -> the (father, mother) names its Birth records give, for this slot's
    village (every numbered file of A New Home's Births and Conceptions log)."""
    out: dict[tuple[str, int, int], set[tuple[str, str]]] = {}
    logs = Path(folder) / layout.LOGS
    for path in sorted(logs.rglob("Virtual Villagers 1 Births and Conceptions Log *.txt")):
        if not path.is_file() or not re.search(r"Log \d+\.txt$", path.name):
            continue
        try:
            text = path.read_bytes().decode("latin-1")
        except OSError:
            continue
        ours = False
        for block in re.split(r"\r?\n\s*\r?\n", text):
            lines = block.strip("\r\n").splitlines()
            for ln in lines:
                if ln.startswith("Village:"):
                    ours = ln.rstrip().endswith(f"(Save {slot})")
            heads = [ln for ln in lines if ln and not ln.startswith(" ") and not ln.startswith("Village:")]
            if not ours or not heads or not re.match(r"^Birth( \d+)?\s*$", heads[0]):
                continue
            who: dict[str, list] = {}
            cur = None
            for ln in lines:
                m = re.match(r"^\s+(Child|Mother|Father): ?(.*)$", ln)
                if m:
                    cur = m.group(1)
                    who[cur] = [m.group(2).strip(), None, None]
                    continue
                m = re.match(r"^\s+(Head|Body): (-?\d+)", ln)
                if m and cur is not None:
                    k = 1 if m.group(1) == "Head" else 2
                    if who[cur][k] is None:
                        who[cur][k] = int(m.group(2))
                if re.match(r"^\s+(Skills|Born as|Note)", ln):
                    cur = None
            if "Child" in who and who["Child"][1] is not None and who["Child"][2] is not None:
                key = (who["Child"][0], who["Child"][1], who["Child"][2])
                father = who.get("Father", [""])[0]
                mother = who.get("Mother", [""])[0]
                out.setdefault(key, set()).add((father if father != "(unknown)" else "",
                                                mother if mother != "(unknown)" else ""))
    return out


def _slot_blocks(folder: Path, slot: int, pattern: str):
    """Every record block of this slot's village in A New Home's logs matching the file `pattern`."""
    logs = Path(folder) / layout.LOGS
    for path in sorted(logs.rglob(pattern)):
        if not path.is_file() or not re.search(r" \d+\.txt$", path.name):
            continue
        try:
            text = path.read_bytes().decode("latin-1")
        except OSError:
            continue
        ours = False
        for block in re.split(r"\r?\n\s*\r?\n", text):
            lines = block.strip("\r\n").splitlines()
            for ln in lines:
                if ln.startswith("Village:"):
                    ours = ln.rstrip().endswith(f"(Save {slot})")
            heads = [ln for ln in lines if ln and not ln.startswith(" ") and not ln.startswith("Village:")]
            if ours and heads:
                yield heads[0].strip(), lines


def _value(lines: list[str], key: str) -> str | None:
    for ln in lines:
        m = re.match(rf"^\s+{key}: ?(.*)$", ln)
        if m:
            return m.group(1).strip()
    return None


def _dead_names(folder: Path, slot: int) -> set[str]:
    out = set()
    for head, lines in _slot_blocks(folder, slot, "Virtual Villagers 1 Deaths Log *.txt"):
        if head.startswith(("Death", "Disappeared")) and _value(lines, "Name"):
            out.add(_value(lines, "Name"))
    return out


def _arrived_names(folder: Path, slot: int) -> set[str]:
    """Villagers the log says ARRIVED, with a "How:" that says how (not a backfilled "unknown"):
    villagers not born here have no parents (the owner's rule)."""
    out = set()
    for head, lines in _slot_blocks(folder, slot, "Virtual Villagers 1 Births and Conceptions Log *.txt"):
        how = _value(lines, "How") or ""
        if head.startswith("Arrived") and _value(lines, "Name") and how and how.lower() != "unknown":
            out.add(_value(lines, "Name"))
    return out


def plan(folder: Path, slot: int) -> Plan:
    folder = Path(folder)
    path = parents_path(folder, slot)
    if not path.is_file():
        raise RestoreError(f"There is no A New Home parentage file for Save {slot}; nothing to restore.")
    original = path.read_bytes()
    table = read_table(path, slot)
    if table is None:
        raise RestoreError(f"{path.name} is not a parentage file this patcher can read; nothing was changed.")
    result = Plan(path, original, table)
    births = _births_log_parents(folder, slot)
    by_name: dict[str, set[tuple[str, str]]] = {}
    for (child, _h, _b), parents in births.items():
        by_name.setdefault(child, set()).update(parents)
    dead = _dead_names(folder, slot)
    arrived = _arrived_names(folder, slot)
    where: dict[tuple, list[int]] = {}
    for i in range(COUNT):
        ident = table.identity(i)
        if ident is not None:
            where.setdefault(ident, []).append(i)
    done: set[tuple] = set()
    skipped: set[tuple] = set()
    for copy in copies(folder, slot):
        old = read_table(copy, slot)
        if old is None:
            continue
        seen: dict[tuple, list[int]] = {}
        for i in range(COUNT):
            ident = old.identity(i)
            if ident is not None:
                seen.setdefault(ident, []).append(i)
        for ident, at in seen.items():
            if ident in done or ident in skipped:
                continue
            if len(at) != 1:
                if any(old.has_parents(i) for i in at):
                    skipped.add(ident)
                    result.ambiguous.append(ident[0])
                continue
            i = at[0]
            if not old.has_parents(i):
                continue
            now_at = where.get(ident, [])
            if len(now_at) > 1:
                skipped.add(ident)
                result.ambiguous.append(ident[0])
                continue
            if now_at and table.has_parents(now_at[0]):
                done.add(ident)                            # a parent is there now: never changed
                continue
            father, mother = old.names(i)
            if ident[0] in arrived:
                continue                                   # an arrival has no parents: never given any
            if not now_at and ident[0] not in dead:
                # Not in the file now and no Death record under this name: an older name (before Last
                # Names, before a rename) or an entry an older build let drift -- never brought back.
                continue
            head, body = (table.looks(now_at[0]) if now_at else old.looks(i))
            logged = births.get((ident[0], head, body))
            if not now_at and not logged and ident[0] in by_name:
                logged = by_name[ident[0]]                 # the dead: their Birth records by name
            if logged and (father, mother) not in logged:
                skipped.add(ident)
                result.conflicts.append(f"{ident[0]} -- the copy says father {father or '(unknown)'}, mother "
                                        f"{mother or '(unknown)'}; the Births log says "
                                        + "; ".join(f"father {f or '(unknown)'}, mother {m or '(unknown)'}"
                                                    for f, m in sorted(logged)))
                continue
            if now_at:
                table.put_parents(now_at[0], old.parents(i))
                result.restored.append(Restored(ident[0], father, mother, copy.name))
            else:
                free = next((k for k in range(COUNT) if table.empty_record(k)), None)
                if free is None:
                    continue
                o = HEADER + free * OCCUPANT
                src = HEADER + i * OCCUPANT
                table.data[o:o + OCCUPANT] = old.data[src:src + OCCUPANT]
                table.data[o + 1] = 1                      # departed
                table.put_parents(free, old.parents(i))
                where[ident] = [free]
                result.restored.append(Restored(ident[0], father, mother, copy.name, departed=True))
            done.add(ident)
    return result


@dataclass
class Result:
    plan: Plan
    copy: Path | None
    backup: vv_save_backup.BackupResult | None


def _village(folder: Path, slot: int) -> str | None:
    logs = Path(folder) / layout.LOGS
    for path in sorted(logs.rglob("Virtual Villagers 1 Births and Conceptions Log *.txt")):
        try:
            for ln in path.read_bytes().decode("latin-1").splitlines():
                if ln.startswith("Village:") and ln.rstrip().endswith(f"(Save {slot})"):
                    return ln.rstrip()
        except OSError:
            continue
    return None


def restore(folder: Path, slot: int, processes: vv_save_backup.ProcessController | None = None,
            now: datetime | None = None) -> Result:
    folder = Path(folder)
    controller = processes if processes is not None else vv_save_backup.WindowsProcesses()
    tools._refuse_if_running(folder, controller)
    try:
        work = plan(folder, slot)
    except (OSError, struct.error, ValueError) as exc:
        raise RestoreError(f"A file could not be read ({exc}); nothing was changed.") from exc
    if not work.restored:
        return Result(work, None, None)
    backup = vv_save_backup.copy_save_folder(folder, now or datetime.now(), suffix="before parents restore")
    for k in range(1, 1000):
        target = tools.copy_before_repair(folder, work.path, COPY_SUFFIX + ("" if k == 1 else f"-{k}"))
        if not target.exists():
            break
    else:
        raise RestoreError(f"{work.path.name} has too many copies already; nothing was changed.")
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "xb") as copy:
        copy.write(work.original)
    if work.path.read_bytes() != work.original:
        raise RestoreError(f"{work.path.name} changed while it was being read; nothing was changed.")
    temporary = work.path.with_name(work.path.name + ".restore.tmp")
    temporary.write_bytes(bytes(work.table.data))
    os.replace(temporary, work.path)
    fixes = [tools.WordFix(r.name + (" (departed)" if r.departed else "")
                           + f": father {r.father or '(unknown)'}, mother {r.mother or '(unknown)'} from {r.source}",
                           -1, target.name) for r in work.restored]
    tools.note_word_repair(folder, 1, _village(folder, slot), fixes, now,
                           checked="the parents in A New Home's parentage file, against the copies the patcher "
                                   "kept of it (only villagers with no parents now; nothing else changed)",
                           corrected="Parents restored", unit="villager(s)")
    return Result(work, target, backup)
