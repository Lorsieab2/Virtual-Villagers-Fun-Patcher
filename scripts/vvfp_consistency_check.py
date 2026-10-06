"""Cross-check every log and data file the Fun Patcher keeps for one village against its save.

usage:
    python scripts/vvfp_consistency_check.py "<Documents>\\LDW\\<game folder>" <slot> [--game N]

READ-ONLY.  Nothing is written, moved or created; the save, the logs and the .dat files are
only opened for reading.  It prints one section per file with a verdict on each line:

    OK          the file agrees with the save (and with the other files where they overlap)
    WRONG       confirmed wrong against a source of truth; "repairable" says whether the
                game's cross-check repairs it (only when the player says so: Repair Logs, or
                Repair at the quit with "Check logs automatically" on)
    NOTE        a disagreement that is not proof of an error (a log is a lower bound, a log
                written at a later save than the .ldw on disk, a value no source records)
    UNCHECKED   no source of truth exists for it, or the file could not be read

and exits 1 when anything is WRONG, 0 otherwise.

WHAT IS THE SOURCE OF TRUTH, PER FILE (the full table is in docs/first-load-cross-check.md):

  - The save (.ldw) is the truth for who is alive now: name, sex, age, head, body, skills and,
    in VV2-VV5, each villager's own parents.  The patcher's logs are written FROM the game's
    memory at each save, so a log can be AHEAD of the .ldw on disk (a session that saved its
    logs and was then closed without the game writing the slot), never behind it.
  - The Births and Conceptions log is the truth for who was born to whom: it is written at
    the moment of each birth and never rewritten.  It is what A New Home's parentage table
    is rebuilt from.
  - Nothing outside a mask file records a mask, but each entry stores the identity of the villager
    it is for: an entry whose identity no villager in the save carries (a body awaiting burial
    counts) and that shows on nobody is an orphan (v1.35.59), WRONG and repairable.

The save layouts are the games' own (A New Home: +0x33C..+0x3D8 of each record from file
+0x184, the layout scripts/... and the owner's repair tool use; The Secret City and The Tree
of Life: the 150-entry packed table tests/save_table_emulator.py runs the games' own writer
for; The Lost Children and New Believers: the same per-villager window, located by its
names and checked against the Village Population log)."""
from __future__ import annotations

import argparse
import re
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path

GAME_TITLES = {
    1: "A New Home", 2: "The Lost Children", 3: "The Secret City",
    4: "The Tree of Life", 5: "New Believers",
}
SAVE_STEMS = {
    1: "Virtual Villagers", 2: "Virtual Villagers - The Lost Children",
    3: "Virtual Villagers - The Secret City", 4: "Virtual Villagers - The Tree of Life",
    5: "Virtual Villagers - New Believers",
}
DATA = "Virtual Villagers Fun Patcher Data"
LOGS = "Virtual Villagers Fun Patcher Logs"

VERDICTS = ("OK", "WRONG", "NOTE", "UNCHECKED")

# Master status, per game (the statistics exporter's own thresholds).
MASTER = {1: 90, 3: 88, 4: 88, 5: 88}


@dataclass
class Villager:
    rank: int
    name: str
    male: bool
    age: int
    head: int
    body: int
    skills: list[float]
    father: str = ""
    mother: str = ""
    scalar: int = 0            # VV1 family scalar (+0x36C)
    due: int = 0               # VV1 pregnancy field (+0x358)
    raw: bytes = b""           # VV1: the record window +0x33C..+0x3D8
    ident: int = 0             # the Origins companion's mask identity (see mask_identity)
    ident_v2: int = 0          # The Tree of Life's older one (gender and name)
    name_hash: int = 0         # the name-only identity of the older mask files


class CheckError(Exception):
    """The village cannot be checked at all (no save for the slot).  The CLI prints it and exits 1,
    as it always has; the patcher window's Check Logs shows it (src/vv_log_tools.py)."""


@dataclass
class Report:
    lines: list[tuple[str, str, str]] = field(default_factory=list)   # (file, verdict, text)

    def add(self, file: str, verdict: str, text: str) -> None:
        self.lines.append((file, verdict, text))

    @property
    def wrong(self) -> int:
        return sum(v == "WRONG" for _, v, _ in self.lines)

    def counts(self) -> dict[str, int]:
        """How many lines carry each verdict, every verdict listed (0 when none)."""
        out = {verdict: 0 for verdict in VERDICTS}
        for _, verdict, _ in self.lines:
            out[verdict] = out.get(verdict, 0) + 1
        return out

    def render(self) -> str:
        out, current = [], None
        for file, verdict, text in self.lines:
            if file != current:
                out.append("")
                out.append(f"== {file}")
                current = file
            out.append(f"  {verdict:<9} {text}")
        return "\n".join(out).lstrip("\n")


# ---- the save -------------------------------------------------------------------------------

def cstr(data: bytes, offset: int, capacity: int) -> str:
    return data[offset:offset + capacity].split(b"\0", 1)[0].decode("latin-1")


def i32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<i", data, offset)[0]


def f32(data: bytes, offset: int) -> float:
    return struct.unpack_from("<f", data, offset)[0]


VV1_BLOCK0, VV1_STRIDE, VV1_BASE = 0x184, 0x9C, 0x33C


def vv1_roster(data: bytes) -> list[Villager]:
    """A New Home: the save keeps record bytes +0x33C..+0x3D8 of all 256 records, packed, from
    file +0x184; +0x3D4 is 1 for every villager the save holds (the repair tool's rule)."""
    if len(data) < VV1_BLOCK0 + 256 * VV1_STRIDE:
        raise ValueError(f"{len(data)} bytes is not an A New Home save")
    out = []
    for i in range(256):
        base = VV1_BLOCK0 + i * VV1_STRIDE

        def f(off: int) -> int:
            return i32(data, base + off - VV1_BASE)
        name = cstr(data, base + 0x370 - VV1_BASE, 0x1B)
        gender = f(0x350)
        if f(0x3D4) != 1 or not name or gender not in (1, 2):
            continue
        raw = data[base:base + VV1_STRIDE]
        # vv1_mask_identity (native/vv1_origins_icons): name (to 0x1C bytes), 0xFF, gender, the family scalar.
        h = _fnv_text(FNV_BASIS, raw[0x370 - VV1_BASE:0x370 - VV1_BASE + 0x1C])
        h = _fnv(h, b"\xff" + raw[0x350 - VV1_BASE:0x354 - VV1_BASE] + raw[0x36C - VV1_BASE:0x370 - VV1_BASE])
        ident = h or 1
        out.append(Villager(rank=len(out), name=name, male=gender == 1, age=f(0x348), head=f(0x360),
                            body=f(0x364), skills=[f(0x3BC + 4 * k) for k in range(5)],
                            scalar=f(0x36C), due=f(0x358),
                            raw=raw, ident=ident))
    return out


# ---- the Origins companions' mask identities (FNV-1a, as each companion computes it) ----------

FNV_BASIS, FNV_PRIME = 2166136261, 16777619


def _fnv(h: int, data: bytes) -> int:
    for b in data:
        h = ((h ^ b) * FNV_PRIME) & 0xFFFFFFFF
    return h


def _fnv_text(h: int, field: bytes) -> int:
    """The bytes of a name field up to its terminator."""
    return _fnv(h, field.split(b"\0", 1)[0])


def mask_identity(game: int, data: bytes, p: int, lay: SaveLayout) -> tuple[int, int, int]:
    """(identity, The Tree of Life's version-2 identity, name hash) of the saved villager whose name is
    at data[p]: the identity each game's Origins companion stores with a mask entry (the record
    fields the save keeps; see the companions' vv2_roster_identities, vv3_mask_fingerprint,
    vv_fingerprint and vv5_identity)."""
    name = data[p:p + lay.name_cap]
    sex = data[p + lay.gender:p + lay.gender + 4]
    father = data[p + lay.father:p + lay.father + lay.parent_cap]
    mother = data[p + lay.mother:p + lay.mother + lay.parent_cap]
    names = (_fnv(_fnv_text(FNV_BASIS, name), b"\xff")) or 1
    if game == 3:
        h = _fnv(FNV_BASIS, sex[:1] + data[p + 0xF0:p + 0xFC] + data[p + 0xFC:p + 0x108])
        return (_fnv(_fnv_text(h, name), b"\xff") or 1), 0, names
    if game == 4:
        v2 = _fnv(_fnv_text(_fnv(FNV_BASIS, sex), name), b"\xff")
        h = _fnv(_fnv_text(v2, father), b"\xfe")
        h = _fnv(_fnv_text(h, mother), b"\xfd")
        return (h or 1), (v2 or 1), names
    h = _fnv(_fnv(_fnv_text(FNV_BASIS, name), b"\xff"), sex)
    h = _fnv(_fnv_text(h, father), b"\xfe")
    h = _fnv(_fnv_text(h, mother), b"\xfd")
    return (h or 1), 0, names


# VV2-VV5: offsets relative to the villager's NAME inside its saved entry.
#   VV3/VV4: entry = u32 flag, then the record windows the games' writers pack (see
#   tests/save_table_emulator.py: VV3 (0xDC4,0xA8)(0xE6C,0x40)(0xEAC,0x18)(0xFB4,0xC)(0xFC0,0xC),
#   VV4 (0x1B8C,0xA8)(0x1C34,0x28)(0x1C5C,0x18)(0x1E60,0x18)); the name is record +0xDD4/+0x1B9C,
#   so entry +20.  VV5 packs the same first window as VV4.  VV2 saves one 0x2E0-byte window.
@dataclass(frozen=True)
class SaveLayout:
    stride: int
    name_cap: int
    gender: int
    male_value: int
    age: int
    head: int
    body: int
    skills: int
    skill_count: int
    skills_float: bool
    father: int | None
    mother: int | None
    parent_cap: int


LAYOUTS = {
    2: SaveLayout(0x2E0, 0x18, -0x2C, 1, -0x34, -0x1C, -0x18, 0x280, 5, False, 0x19, 0x32, 0x18),
    3: SaveLayout(0x11C, 0x19, -0x0C, 1, -0x10, 0x1C, 0x20, 0xD8, 5, False, 0x24, 0x3D, 0x19),
    4: SaveLayout(0x104, 0x19, -0x0C, 1, -0x10, 0x1C, 0x20, 0xC0, 5, True, 0x24, 0x3D, 0x19),
    5: SaveLayout(0x118, 0x19, -0x0C, 1, -0x10, 0x1C, 0x20, 0xC0, 6, True, 0x24, 0x3D, 0x19),
}
NAME_RE = re.compile(rb"[A-Z][A-Za-z0-9' -]{1,23}\0")


def plausible(data: bytes, p: int, lay: SaveLayout) -> bool:
    if p + lay.stride > len(data) or p + min(lay.age, lay.gender, lay.head) < 0:
        return False
    if not NAME_RE.match(data, p):
        return False
    head, body = i32(data, p + lay.head), i32(data, p + lay.body)
    return 0 <= head < 64 and 0 <= body < 64 and 0 <= i32(data, p + lay.age) < 200000


def table_start(data: bytes, lay: SaveLayout, hint_names: list[str]) -> int | None:
    """The save's villager table: the longest run of plausible entries at the stride, the
    first of whose names the Village Population log (when there is one) also lists first."""
    best, best_len = None, 0
    for m in NAME_RE.finditer(data):
        p = m.start()
        n = 0
        while plausible(data, p + n * lay.stride, lay):
            n += 1
        if n > best_len or (n == best_len and best is not None and hint_names
                            and cstr(data, p, lay.name_cap) == hint_names[0]
                            and cstr(data, best, lay.name_cap) != hint_names[0]):
            best, best_len = p, n
    return best


def vv25_roster(game: int, data: bytes, hint_names: list[str]) -> list[Villager]:
    # VV2 keeps all 256 slots in one table; VV3-VV5 keep 150 there and the rest in the extension.
    lay = LAYOUTS[game]
    start = table_start(data, lay, hint_names)
    if start is None:
        raise ValueError("no villager table found")
    out = []
    starts = [start]
    # 256 Villagers (Experimental): villagers 151-256 are kept in an extension the patched game
    # appends to the save, as a second run of the same entries further on.
    end = start
    while plausible(data, end, lay):
        end += lay.stride
    if game != 2:
        # Past the whole 150-entry table, never inside it; one villager is enough (151 living).
        for m in NAME_RE.finditer(data, max(end, start + 150 * lay.stride)):
            if plausible(data, m.start(), lay):
                starts.append(m.start())
                break
    for p in starts:
        out.extend(_entries(data, p, lay, len(out), game))
    return out


def _entries(data: bytes, p: int, lay: SaveLayout, first: int, game: int = 0) -> list[Villager]:
    out = []
    while plausible(data, p, lay):
        ident, ident_v2, name_hash = mask_identity(game, data, p, lay) if game else (0, 0, 0)
        skills = [(f32 if lay.skills_float else i32)(data, p + lay.skills + 4 * k) for k in range(lay.skill_count)]
        out.append(Villager(rank=first + len(out), name=cstr(data, p, lay.name_cap),
                            male=i32(data, p + lay.gender) == lay.male_value,
                            age=i32(data, p + lay.age), head=i32(data, p + lay.head), body=i32(data, p + lay.body),
                            skills=skills,
                            father=cstr(data, p + lay.father, lay.parent_cap) if lay.father is not None else "",
                            mother=cstr(data, p + lay.mother, lay.parent_cap) if lay.mother is not None else "",
                            ident=ident, ident_v2=ident_v2, name_hash=name_hash))
        p += lay.stride
    return out


# ---- the logs -------------------------------------------------------------------------------

@dataclass
class Person:
    name: str
    head: int | None
    body: int | None


@dataclass
class LogRecord:
    kind: str                  # "birth" | "conception" | "arrived"
    village: str               # the full "Village: ..." line
    child: Person | None = None
    mother: Person | None = None
    father: Person | None = None
    babies: int = 0


def numbered(folder: Path, stem: str) -> list[Path]:
    files = []
    if folder.is_dir():
        for p in folder.iterdir():
            m = re.fullmatch(re.escape(stem) + r" (\d+)\.txt", p.name)
            if m and p.is_file():
                files.append((int(m.group(1)), p))
    return [p for _, p in sorted(files)]


def parse_person(lines: list[str], start: int, label: str) -> Person:
    m = re.match(r"\s*%s:\s*(.*)$" % label, lines[start])
    person = Person(m.group(1).strip(), None, None)
    if person.name in ("(unknown)", "(none)"):
        return None                       # WriteParentageBirth's "never captured": no parent
    for line in lines[start + 1:]:
        if re.match(r"\s*(Child|Mother|Father|Skills|Babies in pregnancy|Note)\b", line):
            break
        h = re.match(r"\s*Head:\s*(-?\d+)", line)
        b = re.match(r"\s*Body:\s*(-?\d+)", line)
        if h and person.head is None:
            person.head = int(h.group(1))
        if b and person.body is None:
            person.body = int(b.group(1))
    return person


class BirthsLog(list):
    """The village's records, plus `village` (its latest "Village:" line for the slot, or None)
    and `damaged` (one of its records was cut short: the in-game check reads such a log as
    unreadable and changes nothing)."""
    village: str | None = None
    damaged: bool = False


def whole(p: Person | None) -> bool:
    return p is None or not p.name or (p.head is not None and p.body is not None)


def births_log(game_dir: Path, game: int, slot: int) -> tuple[BirthsLog, list[Path]]:
    """This slot's Birth and Conception records, in log order, from every numbered file (the
    same reading the in-game cross-check and the owner's repair tool do).  The village is the
    slot's LATEST header, whether or not a record follows it yet (Codex, #522: a new village
    whose header is all its file holds so far is not the previous village)."""
    files = numbered(game_dir / LOGS / "Births and Conceptions", f"Virtual Villagers {game} Births and Conceptions Log")
    records: list[LogRecord] = []
    latest = None
    damaged_in: set[str] = set()
    for path in files:
        text = read_log_text(path)
        header = None
        for block in re.split(r"\n\s*\n", text):
            lines = [l for l in block.split("\n") if l.strip()]
            heads = [l for l in lines if l.startswith("Village:")]
            if heads:
                header = heads[-1].rstrip()
                lines = [l for l in lines if not l.startswith("Village:")]
                if header.endswith(f"(Save {slot})"):
                    latest = header
            if not lines or header is None or not header.endswith(f"(Save {slot})"):
                continue
            kind = lines[0].strip()
            rec = LogRecord(kind="", village=header)
            if re.fullmatch(r"Arrived \d+", kind):
                # An Arrived record: "  Name:", "  Head:", "  Body:" (two spaces in).
                fields = {}
                for line in lines[1:]:
                    m = re.match(r"  (Name|Head|Body): (.*)$", line)
                    if m and m.group(1) not in fields:
                        fields[m.group(1)] = m.group(2).strip()
                try:
                    rec.child = Person(fields["Name"], int(fields["Head"]), int(fields["Body"]))
                except (KeyError, ValueError):
                    continue
                rec.kind = "arrived"
                records.append(rec)
                continue
            for k, line in enumerate(lines):
                if re.match(r"\s*Child:", line):
                    rec.child = parse_person(lines, k, "Child")
                    if rec.child is None:
                        rec.child = Person("", None, None)
                elif re.match(r"\s*Mother:", line):
                    rec.mother = parse_person(lines, k, "Mother")
                elif re.match(r"\s*Father:", line):
                    rec.father = parse_person(lines, k, "Father")
                m = re.match(r"\s*Babies in pregnancy:\s*(\d+)", line)
                if m:
                    rec.babies = int(m.group(1))
            if kind == "Birth" or kind.startswith("Conception"):
                main = rec.child if kind == "Birth" else rec.mother
                if (main is None or not main.name or main.head is None or main.body is None
                        or not whole(rec.mother) or not whole(rec.father) or not whole(rec.child)):
                    damaged_in.add(header)        # cut short: the game reads the whole log as unreadable
                    continue
            if kind == "Birth" and rec.child:
                rec.kind = "birth"
            elif kind.startswith("Conception") and rec.mother:
                rec.kind = "conception"
            else:
                continue
            records.append(rec)
    out = BirthsLog(r for r in records if r.village == latest)
    out.village = latest
    out.damaged = latest in damaged_in
    return out, files


class LogUnreadable(Exception):
    pass


def read_log_text(path: Path) -> str:
    try:
        return path.read_text(encoding="latin-1").replace("\r\n", "\n")
    except OSError as exc:            # locked, denied: reported, never a crash (Codex, #522)
        raise LogUnreadable(f"{path.name}: {exc.strerror or exc}") from exc


def numbered_records(game_dir: Path, folder: str, stem: str, marker: str, slot: int) -> tuple[list[str], list[Path]]:
    """The blocks of a numbered log that begin with `marker` and belong to this slot."""
    files = numbered(game_dir / LOGS / folder, stem)
    found: list[tuple[str, str]] = []
    latest = None
    for path in files:
        text = read_log_text(path)
        header = None
        for block in re.split(r"\n\s*\n", text):
            lines = [l for l in block.split("\n") if l.strip()]
            heads = [l for l in lines if l.startswith("Village:")]
            if heads:
                header = heads[-1].rstrip()
                lines = [l for l in lines if not l.startswith("Village:")]
                if header.endswith(f"(Save {slot})"):
                    latest = header
            if header and header.endswith(f"(Save {slot})") and lines and lines[0].startswith(marker):
                found.append((header, "\n".join(lines)))
    # Only the slot's latest village (Codex, #522): an earlier village in the same slot is not this one.
    return [b for h, b in found if h == latest], files


def snapshot_villagers(text: str) -> list[dict]:
    out = []
    for block in re.split(r"\n(?=Villager \d+\n)", text)[1:]:
        v = {"name": "", "head": None, "body": None, "skills": [], "title": None}
        m = re.search(r"\n  Name: (.*)", block)
        if m:
            v["name"] = m.group(1).strip()
        for key in ("Head", "Body", "Age"):
            m = re.search(r"\n  %s: (-?\d+)" % key, block)
            v[key.lower()] = int(m.group(1)) if m else None
        pf = re.search(r"\n  Parents:\n(?:    Father: (.*)\n(?:      .*\n)*)?(?:    Mother: (.*)\n)?", block)
        v["parents"] = (pf.group(1) or "", pf.group(2) or "") if pf else ("", "")
        m = re.search(r"\n  Custom title: (.*)", block)
        if m:
            v["title"] = m.group(1).strip()
        skills = re.search(r"\n  Skills:\n((?:    .*\n?)+)", block)
        if skills:
            v["skills"] = [int(x) for x in re.findall(r"^    \S+\s+(-?\d+)", skills.group(1), re.M)]
        out.append(v)
    return out


def population_for_slot(game_dir: Path, slot: int) -> list[dict] | None:
    folder = game_dir / LOGS / "Tribe Population"
    for path in numbered(folder, "Village Population"):
        text = path.read_text(encoding="latin-1").replace("\r\n", "\n")
        m = re.search(r"^Village: .*\(Save (\d)\)\s*$", text, re.M)
        if m and int(m.group(1)) == slot:
            return snapshot_villagers(text)
    return None


def history_last(game_dir: Path, slot: int) -> tuple[str, list[dict]] | None:
    folder = game_dir / LOGS / "Tribe History"
    last = None
    for path in numbered(folder, "Village History"):
        text = path.read_text(encoding="latin-1").replace("\r\n", "\n")
        for snap in re.split(r"\n(?==== )", "\n" + text):
            m = re.search(r"^Village: .*\(Save (\d)\)\s*$", snap, re.M)
            stamp = re.search(r"^=== .* -- (.*) ===", snap.strip("\n"), re.M)
            if m and int(m.group(1)) == slot:
                last = (stamp.group(1) if stamp else "?", snapshot_villagers(snap))
    return last


# ---- the checks -----------------------------------------------------------------------------

def key(name: str, head, body) -> tuple:
    return (name, head, body)


def enc_body(p: Person | None) -> int:
    return 0 if p is None or p.body is None or not 0 <= p.body <= 253 else p.body + 1


def vv1_parentage(game_dir: Path, slot: int, roster: list[Villager], births: list[LogRecord], rep: Report) -> None:
    """The VV1 parentage table against the Births log -- the in-game cross-check's own rules
    (native/vv1_parentage/vv1_crosscheck.inc), so this tool predicts what it will do."""
    name = f"Virtual Villagers 1 Parentage Records - Save {slot}.dat"
    candidates = [game_dir / DATA / "Parentage Records" / name, game_dir / DATA / name]
    path = next((p for p in candidates if p.is_file()), None)
    label = f"{DATA}\\{name}"
    if path is None:
        rep.add(label, "NOTE", "no parentage file (nothing recorded yet, or the patch is off)")
        return
    data = path.read_bytes()
    if len(data) != 12 + 256 * (36 + 92) or struct.unpack_from("<I", data, 0)[0] != 0x32305056 \
            or struct.unpack_from("<I", data, 8)[0] != slot:
        rep.add(label, "UNCHECKED", f"not a VP02 parentage file for Save {slot} ({len(data)} bytes)")
        return
    entries = 12 + 256 * 36
    rost = []
    for i in range(256):
        o = 12 + i * 36
        rost.append((data[o], data[o + 1], i32(data, o + 4), cstr(data, o + 8, 28)))

    def entry(i):
        o = entries + i * 92
        return dict(fh=data[o], fb=data[o + 1], mh=data[o + 2], mb=data[o + 3], sh=data[o + 4], sb=data[o + 5],
                    father=cstr(data, o + 8, 28), mother=cstr(data, o + 36, 28), stash=cstr(data, o + 64, 28))

    # The file's entries follow its own roster: match each living villager by the roster's
    # identity (gender, family scalar, name), unique on both sides -- what the game's load does.
    def ident_v(v: Villager):
        return (1 if v.male else 2, v.scalar, v.name)
    ids_file = [(g, s, n) for g, _, s, n in rost]
    current = {}
    for v in roster:
        idv = ident_v(v)
        at = [i for i, r in enumerate(rost) if r[0] and (r[0], r[2], r[3]) == idv]
        if len([w for w in roster if ident_v(w) == idv]) == 1 and len(at) == 1:
            current[v.rank] = entry(at[0])
        elif rost[v.rank][0] and (rost[v.rank][0], rost[v.rank][2], rost[v.rank][3]) == idv:
            current[v.rank] = entry(v.rank)
        else:
            current[v.rank] = None
    del ids_file
    if not any(r.kind == "birth" for r in births):
        rep.add(label, "UNCHECKED", "no Birth record for this village in the Births and Conceptions log: "
                                    "nothing to check the parents against")
        return
    bs = [r for r in births if r.kind == "birth"]
    wrong = 0
    for v in roster:
        cur = current.get(v.rank)
        if cur is None:
            rep.add(label, "NOTE", f"{v.name}: no entry follows this villager (a new occupant: unknown)")
            continue
        shared = sum(key(w.name, w.head, w.body) == key(v.name, v.head, v.body) for w in roster)
        matches = [b for b in bs if b.child and key(b.child.name, b.child.head, b.child.body) == key(v.name, v.head, v.body)]
        named = [b for b in bs if b.child and b.child.name == v.name]
        def parents(b):
            return tuple((p.name, p.head, p.body) if p else None for p in (b.father, b.mother))
        agree = all(parents(m) == parents(matches[0]) for m in matches)   # every field, as the game's repair
        has = bool(cur["father"] or cur["mother"] or cur["fh"] or cur["fb"] or cur["mh"] or cur["mb"])
        now = f"father {cur['father'] or '(unknown)'}, mother {cur['mother'] or '(unknown)'}" if has else "no parents"

        def enc(p):
            return 0 if p is None or p.head is None or not 0 <= p.head <= 253 else p.head + 1
        if matches and agree and len(matches) >= shared:
            b = matches[0]
            f, m = b.father, b.mother
            want = (enc(f) if f else 0, (f.body + 1 if f and f.body is not None and 0 <= f.body <= 253 else 0),
                    enc(m) if m else 0, (m.body + 1 if m and m.body is not None and 0 <= m.body <= 253 else 0),
                    f.name if f else "", m.name if m else "")
            got = (cur["fh"], cur["fb"], cur["mh"], cur["mb"], cur["father"], cur["mother"])
            if want == got:
                rep.add(label, "OK", f"{v.name}: {now}, as the Births log says")
            else:
                wrong += 1
                rep.add(label, "WRONG", f"{v.name}: recorded {now}; the Births log says father {want[4] or '(none)'}, "
                                        f"mother {want[5] or '(none)'} (repairable: Repair Logs, or the quit check)")
        elif matches or not named:
            why = "the Birth records disagree" if matches else "no Birth record (a founder or a grown arrival)"
            if has:
                wrong += 1
                rep.add(label, "WRONG", f"{v.name}: recorded {now}, but {why}: set to unknown "
                                        "(repairable: Repair Logs, or the quit check)")
            else:
                rep.add(label, "OK", f"{v.name}: no parents ({why})")
        else:
            rep.add(label, "UNCHECKED", f"{v.name}: Birth records name {v.name}, none with head {v.head} and body "
                                        f"{v.body} (looks changed since birth): {now} left as it is")
        if v.due:
            convs = [k for k, r in enumerate(births) if r.kind == "conception" and r.mother
                     and key(r.mother.name, r.mother.head, r.mother.body) == key(v.name, v.head, v.body)]
            if shared == 1 and convs and not any(r.kind == "birth" and r.mother and key(r.mother.name, r.mother.head, r.mother.body)
                                                 == key(v.name, v.head, v.body) for r in births[convs[-1] + 1:]):
                f = births[convs[-1]].father
                if f and f.name:
                    if cur["stash"] == f.name and cur["sh"] == enc(f) and cur["sb"] == enc_body(f):
                        rep.add(label, "OK", f"{v.name} is expecting {f.name}'s child, as her last conception says")
                    else:
                        wrong += 1
                        rep.add(label, "WRONG", f"{v.name} is expecting: recorded father {cur['stash'] or '(unknown)'}, "
                                                f"her last conception says {f.name} (repairable)")
        elif (shared == 1 and i32(v.raw, 0x35C - VV1_BASE) == 0
              and (cur["stash"] or cur["sh"] or cur["sb"])):
            # A stale expected father: the save says this villager is not expecting (due and litter
            # both 0), yet the table still holds a father for a pregnancy (owner, 2026-10-04).
            wrong += 1
            rep.add(label, "WRONG", f"{v.name} is not expecting, but an expected father "
                                    f"{cur['stash'] or '(unnamed)'} is still recorded (stale: cleared on repair)")
    if not wrong:
        rep.add(label, "OK", "every living villager's recorded parents agree with the Births log")


def births_marker(game_dir: Path, game: int, slot: int) -> bool:
    p = game_dir / DATA / "Births" / f"Virtual Villagers {game} Births Recorded - Save {slot}.dat"
    if not p.is_file():
        return False
    data = p.read_bytes()
    return len(data) == 16 and struct.unpack("<4I", data) == (0x31424356, 1, game, slot)


def missing_births(roster: list[Villager], births: list[LogRecord]) -> list[Villager]:
    """The in-game backfill's rule (native/parentage_export/arrival_backfill.inc): the villagers
    whose save record keeps parents (born here) with neither a Birth nor an Arrived record of the
    same name, head and body -- counted, so two alike need two -- or, failing that, a record of
    their name that only they carry (looks changed since)."""
    keys = [key(r.child.name, r.child.head, r.child.body) for r in births
            if r.kind in ("birth", "arrived") and r.child and r.child.name]
    taken: dict[tuple, int] = {}
    out = []
    for v in roster:
        if not (v.father or v.mother):
            continue
        k = key(v.name, v.head, v.body)
        have = keys.count(k)
        if have > taken.get(k, 0):
            taken[k] = taken.get(k, 0) + 1
            continue
        named = [x for x in keys if x[0] == v.name]
        if len(named) == 1 and sum(w.name == v.name for w in roster) == 1 and not taken.get(k):
            continue
        out.append(v)
    return out


def vv25_parents_vs_births(roster: list[Villager], births: list[LogRecord], rep: Report, game: int,
                           game_dir: Path | None = None, slot: int = 0) -> None:
    label = f"{LOGS}\\Births and Conceptions (against the save's own parent fields)"
    if game_dir is not None and births.village is not None:
        lacking = missing_births(roster, births)
        done = births_marker(game_dir, game, slot)
        for v in lacking:
            heathen = " (New Believers: a Heathen is never recorded -- the save's faction byte is not read " \
                      "here)" if game == 5 else ""
            if done:
                rep.add(label, "NOTE", f"{v.name}: parents in the save, no Birth record, but this slot's backfill "
                                       f"has already run (born since, and not seen by the game's log){heathen}")
            else:
                rep.add(label, "WRONG", f"{v.name}: born here (the save names father {v.father or '(none)'}, mother "
                                        f"{v.mother or '(none)'}) but no Birth or Arrived record in the Births log "
                                        f"(repairable: a Birth record is written from the save, \"Recorded "
                                        f"afterwards\"){heathen}")
        if not lacking:
            rep.add(label, "OK", "every living villager the save says was born here has a Birth or Arrived record")
    bs = [r for r in births if r.kind == "birth"]
    checked = 0
    for v in roster:
        matches = [b for b in bs if b.child and key(b.child.name, b.child.head, b.child.body) == key(v.name, v.head, v.body)]
        if len(matches) != 1 or sum(key(w.name, w.head, w.body) == key(v.name, v.head, v.body) for w in roster) != 1:
            continue
        b = matches[0]
        f = b.father.name if b.father else ""
        m = b.mother.name if b.mother else ""
        checked += 1
        if (f, m) != (v.father, v.mother):
            rep.add(label, "NOTE", f"{v.name}: the save says father {v.father or '(none)'}, mother {v.mother or '(none)'}; "
                                   f"the Birth record says {f or '(none)'} and {m or '(none)'} (the game's own record is the "
                                   "truth here; the log is not rewritten)")
    rep.add(label, "OK", f"{checked} living villagers with one Birth record compared with the parents the save keeps")


def check_population(game_dir: Path, slot: int, roster: list[Villager], rep: Report) -> None:
    label = f"{LOGS}\\Tribe Population"
    rep.add(label, "NOTE", REPORT_ONLY["population"])
    pop = population_for_slot(game_dir, slot)
    if pop is None:
        rep.add(label, "UNCHECKED", f"no Village Population log for Save {slot}")
        return
    names_log = sorted(v["name"] for v in pop)
    names_save = sorted(v.name for v in roster)
    if names_log == names_save:
        mism = [v.name for v, p in zip(roster, pop) if (p["head"], p["body"]) != (v.head, v.body)]
        if mism:
            rep.add(label, "NOTE", f"same villagers as the save, but head/body differ for {', '.join(mism[:8])}")
        else:
            rep.add(label, "OK", f"the {len(pop)} villagers listed are the save's, with the same looks")
    else:
        only_log = sorted(set(names_log) - set(names_save))
        only_save = sorted(set(names_save) - set(names_log))
        rep.add(label, "NOTE", f"lists {len(pop)} villagers, the save {len(roster)}"
                               + (f"; only in the log: {', '.join(only_log[:8])}" if only_log else "")
                               + (f"; only in the save: {', '.join(only_save[:8])}" if only_save else "")
                               + " (the log is rewritten at every save; it is from a different save point than "
                                 "the .ldw on disk, and comes out right at the next save)")


REPORT_ONLY = {
    "population": "not repaired at load: it is rewritten from the game at every save, from the same memory the save "
                  "is written from; a copy written at load would record the load-time catch-up the save may never "
                  "keep, and the writer also files the Births log's held records early",
    "history": "never rewritten (owner rule); a snapshot is appended at every save, so the next save's snapshot is "
               "the save's -- one appended at load would record unsaved state (see the Population log)",
    "rosters": "not rebuilt: each is the record of the LAST SAVE that the next save compares with -- a mismatch is "
               "the evidence it uses (a different village in the slot; villagers who left unaccounted for), and "
               "rebuilding it from the loaded village would erase that evidence",
    "masks": "an entry whose stored identity no villager in the save carries, on a record nobody holds (The Secret "
             "City: anywhere), shows on nobody and is repaired by the first-load check (after asking); an entry "
             "some villager carries -- one, or several alike -- is never touched",
    "titles": "not repaired: a title of a dead villager is not an orphan, and graves keep no likes or dislikes, so "
              "no file can prove a title belongs to nobody; one shows only on the villager whose fingerprint it "
              "carries",
    "stews": "not repaired: The Secret City and The Tree of Life keep no record of the stews made, and The Lost "
             "Children's found-recipe flags name recipes, not the herb combinations this file counts",
    "game_rows": "Highest Population, Oldest Villager, Babies Made, Triplets Birthed, Tech Points, People Cured, "
                 "Mushrooms Found, Island Events Seen, Puzzles Solved (and Twins Birthed outside The Lost Children) "
                 "are the GAME's own counters, kept in the save and printed as they are at every save: the log "
                 "cannot disagree with the save, and the patcher never changes the game's own counters",
    "unbounded": "Food Gathered (The Tree of Life, New Believers), Debris Cleared and Heathens Converted: no save field "
                 "or log bounds them (the Arrived records' \"Converted from the Heathens\" also follow the Maker's "
                 "conversions, which do not count)",
}


def check_history(game_dir: Path, slot: int, roster: list[Villager], rep: Report) -> None:
    label = f"{LOGS}\\Tribe History (checked only: never rewritten)"
    rep.add(label, "NOTE", REPORT_ONLY["history"])
    last = history_last(game_dir, slot)
    if last is None:
        rep.add(label, "UNCHECKED", f"no Village History snapshot for Save {slot}")
        return
    stamp, snap = last
    if sorted(v["name"] for v in snap) == sorted(v.name for v in roster):
        rep.add(label, "OK", f"the last snapshot ({stamp}) lists the save's {len(roster)} villagers")
    else:
        rep.add(label, "NOTE", f"the last snapshot ({stamp}) lists {len(snap)} villagers, the save {len(roster)} "
                               "(a snapshot is written at a save; the .ldw may be from another)")


def is_elder(game: int, v: Villager) -> bool:
    t = MASTER.get(game)
    return t is not None and sum(1 for s in v.skills if s >= t) >= 3


def check_elders(game_dir: Path, slot: int, game: int, roster: list[Villager], rep: Report) -> int | None:
    label = f"{DATA}\\Village Elders\\Village Elders - Save {slot}.dat"
    path = game_dir / DATA / "Village Elders" / f"Village Elders - Save {slot}.dat"
    if game == 2:
        return None                              # The Lost Children keeps its own elder counter
    if not path.is_file():
        rep.add(label, "UNCHECKED", "no Village Elders file")
        return None
    lines = path.read_text(encoding="latin-1").replace("\r\n", "\n").split("\n")
    if len(lines) < 2 or lines[0] != f"VVFP VILLAGE ELDERS v2 game={game}" or not lines[1].startswith("graves_seen="):
        rep.add(label, "UNCHECKED", "not a v2 Village Elders file for this game")
        return None
    rows = [l.split("\t") for l in lines[2:] if l]
    if any(len(r) < 7 for r in rows):
        rep.add(label, "UNCHECKED", "a line of the Village Elders file is not a whole line")
        return None
    open_lines = [r for r in rows if r[0] == "E" and r[6] == "1"]
    living_elders = [v for v in roster if is_elder(game, v)]
    for r in open_lines:
        if not any(v.name == r[2] and (game == 1 or (v.father, v.mother) == (r[3], r[4])) for v in living_elders):
            rep.add(label, "NOTE", f"open line for {r[2]}, who is not a living elder in this save "
                                   "(closed at the next save if the save is current)")
    for v in living_elders:
        if not any(v.name == r[2] and (game == 1 or (v.father, v.mother) == (r[3], r[4])) for r in open_lines):
            rep.add(label, "NOTE", f"{v.name} is an elder in this save with no open line (added at the next save)")
    # Pre-v1.35.57 drift left closed, not-gone duplicates of a line that is still open.
    for r in rows:
        if r[0] == "E" and r[6] == "0" and r[5] == "0":
            twin = [o for o in open_lines if o[2:5] == r[2:5]]
            if twin and game != 1:
                rep.add(label, "NOTE", f"a closed line for {r[2]} ({r[3] or '-'}/{r[4] or '-'}) duplicates an open one "
                                       "(left by the old record-index drift; it may stand for a dead elder whose line "
                                       "was renamed, so it is reported, not removed)")
    if game == 5:
        rep.add(label, "NOTE", "New Believers: heathens are not elders, and the save's tribe byte is not read here, "
                               "so a heathen elder would show above as 'no open line'; its History log lists the "
                               "Heathens too (the Heathen Chief has every skill at 100), so it cannot prove an elder: "
                               "not repaired")
    if game in (1, 3, 4):
        for v in history_elders(game_dir, slot, game, roster, {r[2] for r in rows}):
            rep.add(label, "WRONG", f"{v['name']} is a Village Elder in the Village History log (Master in 3 or more "
                                    "skills), no longer alive, and on no line of the list (repairable: added as a "
                                    "closed line)")
    rep.add(label, "OK", f"{len(rows)} lines, {len(open_lines)} open; {len(living_elders)} living elders in the save")
    return len(rows)


def history_snapshots(game_dir: Path, header: str) -> list[list[dict]]:
    """Every snapshot of the village whose "Village:" line is `header`, in every numbered file."""
    out = []
    for path in numbered(game_dir / LOGS / "Tribe History", "Village History"):
        text = read_log_text(path)
        for snap in re.split(r"\n(?==== )", "\n" + text):
            m = re.search(r"^(Village: .*)$", snap, re.M)
            if m and m.group(1).rstrip() == header:
                out.append(snapshot_villagers(snap))
    return out


def history_elders(game_dir: Path, slot: int, game: int, roster: list[Villager], listed: set[str]) -> list[dict]:
    """statistics_reconcile.inc's rule: a villager a snapshot of THIS village shows with Master (the game's
    threshold) in 3+ skills, not alive now (the save adds the living), whose name is on no line."""
    births, _ = births_log(game_dir, game, slot)
    header = births.village
    if header is None:
        # No Births log: the slot's latest History header names the village.
        for path in numbered(game_dir / LOGS / "Tribe History", "Village History"):
            for m in re.finditer(r"^(Village: .*\(Save %d\))\s*$" % slot, read_log_text(path), re.M):
                header = m.group(1)
    if header is None:
        return []
    living = {v.name for v in roster}
    found: list[dict] = []
    for snap in history_snapshots(game_dir, header):
        for v in snap:
            if sum(s >= MASTER[game] for s in v["skills"]) < 3 or not v["name"]:
                continue
            if v["name"] in living or v["name"] in listed:
                continue
            if not any(f["name"] == v["name"] and f.get("parents") == v.get("parents") for f in found):
                found.append(v)
    return found


def read_stats_text(game_dir: Path, slot: int) -> dict[str, str] | None:
    folder = game_dir / LOGS / "Village Statistics"
    for name in (f"Village Statistics v2 - Save {slot}.txt", f"Village Statistics - Save {slot}.txt"):
        p = folder / name
        if p.is_file():
            rows = {}
            for line in p.read_text(encoding="latin-1").splitlines():
                m = re.match(r"^([A-Za-z' ]+):\s*(.*)$", line)
                if m and m.group(1) != "Village":
                    rows[m.group(1).strip()] = m.group(2).strip()
            return rows
    return None


def check_statistics(game_dir: Path, slot: int, game: int, roster: list[Villager], births: list[LogRecord],
                     deaths: int, elders: int | None, rep: Report) -> None:
    label = f"{LOGS}\\Village Statistics"
    rows = read_stats_text(game_dir, slot)
    if rows is None:
        rep.add(label, "UNCHECKED", f"no Village Statistics log for Save {slot}")
        return

    def num(k):
        m = re.match(r"-?\d+", rows.get(k, ""))
        return int(m.group(0)) if m else None
    hp = num("Highest Population")
    if hp is not None:
        rep.add(label, "OK" if hp >= len(roster) else "NOTE",
                f"Highest Population {hp} {'>=' if hp >= len(roster) else '<'} the {len(roster)} living now"
                + ("" if hp >= len(roster) else " (the log is from an earlier save)"))
    oldest = num("Oldest Villager")
    if oldest is not None and roster:
        now = max(v.age for v in roster) // 20
        rep.add(label, "OK" if oldest >= now else "NOTE",
                f"Oldest Villager {oldest} {'>=' if oldest >= now else '<'} the oldest living now ({now})")
    babies = num("Babies Made")
    nb = sum(r.kind == "birth" for r in births)
    if babies is not None:
        rep.add(label, "OK" if babies >= nb else "NOTE",
                f"Babies Made {babies} {'>=' if babies >= nb else '<'} the {nb} Birth records in the log "
                "(the log is a lower bound: births before it began are not in it)")
    twins = num("Twins Birthed")
    nt = sum(r.kind == "conception" and r.babies == 2 for r in births)
    if twins is not None:
        rep.add(label, "OK" if twins >= nt else "NOTE",
                f"Twins Birthed {twins} {'>=' if twins >= nt else '<'} the {nt} twin conceptions in the log")
    ve = num("Village Elders")
    if ve is not None and elders is not None:
        rep.add(label, "OK" if ve == elders else "NOTE",
                f"Village Elders {ve} {'=' if ve == elders else '!='} the {elders} lines of the elders file"
                + ("" if ve == elders else " (the log is from another save than the file)"))


def read_counters(game_dir: Path, slot: int, game: int) -> dict[str, int] | None:
    p = game_dir / DATA / "Village Statistics" / f"Village Statistics - Save {slot}.dat"
    if not p.is_file():
        return None
    lines = p.read_text(encoding="latin-1").replace("\r\n", "\n").split("\n")
    if not lines or lines[0] != f"VVFP VILLAGE STATISTICS v1 game={game}":
        return None
    out = {}
    for line in lines[1:]:
        m = re.fullmatch(r"([a-z0-9_.]+)=(-?\d+)", line)
        if m:
            out[m.group(1)] = int(m.group(2))
    return out


def check_counters(game_dir: Path, slot: int, game: int, births: list[LogRecord], graves: int, rep: Report) -> None:
    """statistics_reconcile.inc: Villagers Buried >= this village's Death records with a grave; The Lost
    Children's Twins Birthed >= its twin conceptions.  Raised at the next save after Repair, never lowered.
    (The memorial's graves and The Secret City's living chief are bounds too, read by the game only.)"""
    label = f"{DATA}\\Village Statistics\\Village Statistics - Save {slot}.dat"
    rep.add(label, "NOTE", "reported only: " + REPORT_ONLY["game_rows"])
    rep.add(label, "NOTE", "reported only: " + REPORT_ONLY["unbounded"])
    counters = read_counters(game_dir, slot, game)
    if counters is None:
        rep.add(label, "UNCHECKED", "no counters file this companion would read (it is made at the next save)")
        return
    checks = [("villagers_buried", "Villagers Buried", graves, "Death records with a grave in the Deaths log")]
    if game == 2:
        checks.append(("twins_birthed", "Twins Birthed", sum(r.kind == "conception" and r.babies == 2 for r in births),
                       "twin conceptions in the Births log"))
    for k, row, bound, what in checks:
        if k not in counters:
            rep.add(label, "NOTE", f"{row}: not in the file yet (started at the next save)")
        elif counters[k] < bound:
            rep.add(label, "WRONG", f"{row} is {counters[k]}, below the {bound} {what} (repairable: raised to {bound})")
        else:
            rep.add(label, "OK", f"{row} {counters[k]} >= the {bound} {what}")


VV_MASK_FILES = {1: "Virtual Villagers 1 Village Masks - Save {slot}.dat",
                 2: "Virtual Villagers 2 Village Masks - Save {slot}.dat"}
MASK_NAMES = ("(None)", "Blue Mask", "Orange Mask", "Red Mask", "Purple Mask", "Tribal Chief Mask")


@dataclass
class MaskFile:
    values: list[int]                  # per entry (by record, The Secret City by entry)
    stored: list[int]                  # the identity stored with each entry (0: none)
    roster: list[int] | None           # who held each record when written (None: not kept)
    weak: bool = False                 # name hashes ('VM04', 'VM05' / 'VM25')
    v2: bool = False                   # The Tree of Life version 2 (gender and name)
    legacy: bool = False               # 'VM01': record indexes and nothing else


def _u32s(data: bytes, at: int, n: int) -> list[int]:
    return list(struct.unpack_from(f"<{n}I", data, at))


def _nibbles(data: bytes, at: int, n: int) -> list[int]:
    return [(data[at + (i >> 1)] >> 4 if i & 1 else data[at + (i >> 1)]) & 0x0F for i in range(n)]


def read_mask_file(game: int, data: bytes) -> MaskFile | None:
    """Each companion's format (native/shared/mask_follow.h and the Origins companions); None when the
    companion would not read it either."""
    magic = data[:4]
    if game == 1 and magic in (b"VM01", b"VM02") and len(data) >= 4 + 128:
        values = _nibbles(data, 4, 256)
        if magic == b"VM01":
            return MaskFile(values, [0] * 256, None, legacy=True)
        if len(data) >= 4 + 128 + 1024:
            roster = _u32s(data, 132, 256)
            return MaskFile(values, roster, roster)
    if game == 2 and magic in (b"VM04", b"VM06") and len(data) >= 4 + 1024 + 256:
        roster = _u32s(data, 4, 256)
        return MaskFile(list(data[1028:1284]), roster, roster, weak=magic == b"VM04")
    if game == 3 and magic == b"MSK4" and len(data) >= 4 + 256 + 1024:
        return MaskFile(list(data[4:260]), _u32s(data, 260, 256), None)
    if game == 4 and magic == b"VVMK" and len(data) >= 12:
        version, count = struct.unpack_from("<II", data, 4)
        if count in (150, 256) and version in (2, 3) and len(data) >= 12 + count * (9 if version == 3 else 5):
            return MaskFile(list(data[12:12 + count]), _u32s(data, 12 + count, count),
                            _u32s(data, 12 + count * 5, count) if version == 3 else None, v2=version == 2)
    if game == 5 and magic in (b"VM05", b"VM25", b"VM06", b"VM26"):
        count = 150 if magic in (b"VM05", b"VM06") else 256
        if len(data) >= 4 + count * 4 + count // 2:
            roster = _u32s(data, 4, count)
            return MaskFile(_nibbles(data, 4 + count * 4, count), roster, roster, weak=magic in (b"VM05", b"VM25"))
    return None


def mask_follow(value: list[int], stored: list[int], roster: list[int] | None, live: list[int],
                down_only: bool) -> tuple[list[int], list[int]]:
    """native/shared/mask_follow.h's vv_mask_follow, line for line: what the next load does to the table."""
    n = len(value)

    def count(ids, only, x):
        return sum(1 for i in range(n) if ids[i] == x and (only is None or only[i] != 0))

    def moved_any() -> bool:
        if roster is None:
            return True
        for i in range(n):
            if roster[i] and live[i] and roster[i] != live[i]:
                return True
            if roster[i] and not live[i] and count(live, None, roster[i]) > 0:
                return True
        return False
    repacked = moved_any()
    target = [-1] * n
    for i in range(n):
        if not value[i] or not stored[i]:
            continue
        if (count(stored, value, stored[i]) == 1 and (roster is None or count(roster, None, stored[i]) <= 1)
                and count(live, None, stored[i]) == 1):
            where = live.index(stored[i])
            if not (down_only and where > i):
                target[i] = where
                repacked = repacked or where != i
    for i in range(n):
        if value[i] and stored[i] and target[i] < 0 and not repacked and live[i] == stored[i]:
            target[i] = i
    new_value, new_stored = [0] * n, [0] * n
    for i in range(n):
        if value[i] and target[i] >= 0:
            new_value[target[i]], new_stored[target[i]] = value[i], stored[i]
    for i in range(n):
        if value[i] and target[i] < 0 and not live[i]:
            new_value[i], new_stored[i] = value[i], stored[i]
    return new_value, new_stored


def roster_same(a: list[int], b: list[int]) -> bool:
    """The Lost Children's and New Believers' village match (a strict majority of the smaller roster,
    at the same record or at its rank)."""
    la, lb = sum(1 for x in a if x), sum(1 for x in b if x)
    need = min(la, lb)
    if need == 0:
        return False
    n = rank = 0
    for i, x in enumerate(a):
        if not x:
            continue
        if x == b[i] or (rank < len(b) and x == b[rank]):
            n += 1
        rank += 1
    return n >= need // 2 + 1


def check_masks(game_dir: Path, slot: int, game: int, roster: list[Villager], rep: Report) -> None:
    """Orphan entries (v1.35.59): emulates the companion's next load (the follow), then its scan
    (native/shared/orphan_masks.h).  The loaded village is the save's: it loads packed, villager
    after villager into records 0, 1, 2, ..."""
    name = VV_MASK_FILES.get(game, "Village Masks - Save {slot}.dat").format(slot=slot)
    candidates = [game_dir / DATA / "Village Masks" / name, game_dir / DATA / name]
    path = next((p for p in candidates if p.is_file()), None)
    label = f"{DATA}\\Village Masks\\{name}"
    if path is None:
        rep.add(label, "NOTE", "no mask file")
        return
    data = path.read_bytes()
    masks = read_mask_file(game, data)
    if masks is None:
        rep.add(label, "UNCHECKED", f"{len(data)} bytes, magic {data[:4]!r}: not a mask file the game reads (the "
                                    "companion sets it aside unread)")
        return
    n = len(masks.values)
    live = [0] * n
    live_v2 = [0] * n
    names = [0] * n
    for v in roster[:n]:
        live[v.rank], live_v2[v.rank], names[v.rank] = v.ident, v.ident_v2, v.name_hash
    values = [x if x < len(MASK_NAMES) else 0 for x in masks.values]
    against = names if masks.weak else (live_v2 if masks.v2 else live)
    if masks.legacy or game == 3:
        after, ids = values, masks.stored
    else:
        if game in (2, 5) and not roster_same(masks.roster, against):
            rep.add(label, "NOTE", "another village's mask file (its roster shares no majority with the save): the "
                                   "game ignores it and the village's first mask replaces it")
            return
        after, ids = mask_follow(values, masks.stored, masks.roster, against, masks.weak)
        if masks.weak:
            # vv_om_from_names: a name hash becomes the identity of a villager with that name.
            ids = [(live[i] if names[i] == x else next((live[j] for j in range(n) if names[j] == x), 0)) if x else 0
                   for i, x in enumerate(ids)]
        if masks.v2:
            # The first follow rewrites version 2 as version 3: an entry with no villager to take an
            # identity from is dropped.
            after = [x if live[i] else 0 for i, x in enumerate(after)]
            ids = [live[i] if x else 0 for i, x in enumerate(after)]
    kept = orphans = 0
    for i in range(n):
        if values[i] and not after[i]:
            orphans += 1
            rep.add(label, "WRONG", f"entry {i + 1}: {MASK_NAMES[values[i]]} -- on a record someone else holds now, "
                                    "for no villager the save holds (repairable: the next load drops it on its own)")
    for i in range(n):
        if not after[i]:
            continue
        held = game != 3 and live[i] != 0
        if not held and (ids[i] == 0 or ids[i] not in live):
            orphans += 1
            what = (f"kept for a villager who is no longer in the village (identity {ids[i]:08X})" if ids[i]
                    else "kept with no villager's identity")
            rep.add(label, "WRONG", f"{'entry' if game == 3 else 'record'} {i + 1}: {MASK_NAMES[after[i]]} -- {what} "
                                    "(repairable: the first-load check removes it, after asking)")
        else:
            kept += 1
    if not orphans:
        rep.add(label, "OK", f"{kept} mask entr{'y' if kept == 1 else 'ies'}, each for a villager the save holds")
    else:
        rep.add(label, "NOTE", f"{kept} other mask entr{'y' if kept == 1 else 'ies'} kept: " + REPORT_ONLY["masks"])


def check_titles(game_dir: Path, slot: int, game: int, roster: list[Villager], hist, rep: Report) -> None:
    label = f"{DATA}\\Custom Titles\\Custom Titles - Save {slot}.dat"
    path = game_dir / DATA / "Custom Titles" / f"Custom Titles - Save {slot}.dat"
    if not path.is_file():
        rep.add(label, "NOTE", "no custom titles")
        return
    data = path.read_bytes()
    if len(data) < 16 or data[:4] != b"VCT1" or struct.unpack_from("<I", data, 4)[0] != 2 \
            or struct.unpack_from("<I", data, 8)[0] != game:
        rep.add(label, "UNCHECKED", "not a v2 Custom Titles file for this game")
        return
    count = struct.unpack_from("<I", data, 12)[0]
    if len(data) != 16 + 40 * count:
        rep.add(label, "UNCHECKED", f"{len(data)} bytes does not hold {count} titles")
        return
    for k in range(count):
        o = 16 + 40 * k
        index, fp = struct.unpack_from("<II", data, o)
        title = cstr(data, o + 8, 32)
        if game == 1 and index < 256:
            v = next((w for w in roster if w.rank == index), None)
            ident = None
            if v is not None:
                rec = bytearray(0x3D8)
                rec[0x33C:0x3D8] = v.raw
                h = 2166136261
                for c in rec[0x370:0x370 + 0x1C]:
                    if c == 0:
                        break
                    h = ((h ^ c) * 16777619) & 0xFFFFFFFF
                h = ((h ^ 0xFF) * 16777619) & 0xFFFFFFFF
                for c in bytes(rec[0x398:0x3A8]) + bytes(rec[0x3A8:0x3B8]):
                    h = ((h ^ c) * 16777619) & 0xFFFFFFFF
                ident = h or 1
            if ident == fp:
                rep.add(label, "OK", f"\"{title}\" is on {v.name}, record {index}, as its identity says")
            else:
                rep.add(label, "NOTE", f"\"{title}\" at record {index} does not match the villager there "
                                       "(the game's load moves it to its villager, or shows it on nobody)")
        else:
            rep.add(label, "UNCHECKED", f"\"{title}\" at record {index}: this game's likes and dislikes are not read "
                                        "from the save here, so the identity is not recomputed")
    rep.add(label, "NOTE", REPORT_ONLY["titles"])
    if hist is not None:
        titled = [v for v in hist[1] if v.get("title")]
        rep.add(label, "OK", f"{count} titles in the file; the last History snapshot shows {len(titled)} "
                             "(a title the player removed is not an error, so a difference is not repaired)")


def check_graves(game_dir: Path, slot: int, game: int, deaths: int, rep: Report) -> None:
    if game not in (1, 2):
        return
    name = f"Virtual Villagers {game} Graves - Save {slot}.dat"
    candidates = [game_dir / DATA / "Graves" / name, game_dir / DATA / name]
    path = next((p for p in candidates if p.is_file()), None)
    label = f"{DATA}\\{name}"
    if path is None:
        rep.add(label, "NOTE", "no graves file")
        return
    data = path.read_bytes()
    if len(data) < 16 or data[:4] != b"VCD1":
        rep.add(label, "UNCHECKED", "not a VCD1 graves file")
        return
    count = struct.unpack_from("<I", data, 12)[0]
    if len(data) != 16 + 44 * count:          # checked before any entry is walked (Codex, #522)
        rep.add(label, "UNCHECKED", f"{len(data)} bytes does not hold the {count} entries its header claims")
        return
    graves = sum(struct.unpack_from("<H", data, 16 + 44 * k)[0] == 0 for k in range(count))
    rep.add(label, "OK",
            f"{count} entries, {graves} graves; each is used only while its name-and-age fingerprint matches the "
            f"game's own grave, so a drifted entry is ignored, never shown (Deaths log: {deaths} records)")


def vcr1_problem(data: bytes, game: int) -> str | None:
    """roster_validate (native/vvfp_cause_of_death/cod_roster.inc), minus the per-game snapshot
    bounds, which this tool does not keep: None when the game would read the file."""
    if len(data) < 32:
        return "shorter than its header"
    magic, version, g, count, lo, hi = struct.unpack_from("<4sIIIII", data, 0)
    if magic != b"VCR1" or version != 1 or g != game:
        return "not a version 1 roster of this game"
    if hi <= lo or count > 256:
        return "impossible snapshot bounds or count"
    entry = 16 + hi - lo
    if len(data) != 32 + count * entry:
        return f"{len(data)} bytes does not hold {count} entries"
    prev = prev_rank = None
    for i in range(count):
        e = 32 + i * entry
        index, rank = struct.unpack_from("<HH", data, e)
        if (index >= 256 or rank > index or any(data[e + 4:e + 8])
                or (prev is not None and (index <= prev or rank <= prev_rank))):
            return f"entry {i} is out of order or malformed"
        prev, prev_rank = index, rank
    return None


def check_rosters(game_dir: Path, slot: int, game: int, roster: list[Villager], rep: Report) -> None:
    name = f"Virtual Villagers {game} Village Roster - Save {slot}.dat"
    candidates = [game_dir / DATA / "Unaccounted Villagers" / name, game_dir / DATA / name]
    path = next((p for p in candidates if p.is_file()), None)
    label = f"{DATA}\\{name}"
    if path is not None:
        data = path.read_bytes()
        problem = vcr1_problem(data, game)
        if problem is None:
            count = struct.unpack_from("<I", data, 12)[0]
            rep.add(label, "OK", f"{count} villagers recorded at the last save (rewritten at every save from the "
                                 "game's own records; read by rank or record, so compaction cannot mislead it)")
        else:
            rep.add(label, "UNCHECKED", f"not a roster the game would read: {problem}")
    rep.add(f"{DATA}\\Village Rosters", "NOTE", REPORT_ONLY["rosters"])
    stats_roster = game_dir / DATA / "Village Statistics" / f"Village Roster - Save {slot}.dat"
    label = f"{DATA}\\Village Statistics\\Village Roster - Save {slot}.dat"
    if stats_roster.is_file():
        lines = stats_roster.read_text(encoding="latin-1").splitlines()
        rows = [l for l in lines[1:] if l]
        names = sorted(l.split("\t")[1] for l in rows if l.count("\t") == 2)
        if lines and lines[0] == "VVFP VILLAGE ROSTER v1" and any(l.count("\t") != 2 for l in rows):
            # The game reads a row without exactly two tabs as a damaged roster (Codex, #522).
            rep.add(label, "UNCHECKED", "a row without exactly two tabs: the game treats the roster as damaged")
        elif lines and lines[0] == "VVFP VILLAGE ROSTER v1":
            same = names == sorted(v.name for v in roster)
            rep.add(label, "OK" if same else "NOTE",
                    f"{len(names)} villagers" + ("" if same else f" (the save has {len(roster)}; it is rewritten from "
                                                              "the game at every save)"))
        else:
            rep.add(label, "UNCHECKED", "not a v1 Village Roster")
    aside = sorted((game_dir / DATA).rglob(f"*Save {slot}.dat.previous-village-*"))
    for p in aside:
        rep.add(f"{DATA}\\{p.parent.name}", "NOTE",
                f"{p.name}: set aside as another village's by the old roster match (it may have been this "
                "village's; reported, not merged: the counters restarted from the save's own values)")


def check_stews(game_dir: Path, slot: int, game: int, rep: Report) -> None:
    path = game_dir / DATA / "Stew Discoveries" / f"Stew Discoveries - Save {slot}.dat"
    label = f"{DATA}\\Stew Discoveries\\Stew Discoveries - Save {slot}.dat"
    if not path.is_file():
        return
    lines = path.read_text(encoding="latin-1").splitlines()
    ok = lines and lines[0] == f"VVFP STEW DISCOVERIES v1 game={game}" and all(
        re.fullmatch(r"stew=\d+ herbs=[0-9A-F]{2},[0-9A-F]{2},[0-9A-F]{2}( water=(fresh|salt))?", l) for l in lines[1:] if l)
    rep.add(label, "OK" if ok else "UNCHECKED",
            f"{len(lines) - 1} discoveries, well formed" if ok else "not a well-formed v1 stew file")
    rep.add(label, "NOTE", REPORT_ONLY["stews"])


def check_unaccounted(game_dir: Path, slot: int, game: int, rep: Report) -> int:
    deaths, _ = numbered_records(game_dir, "Deaths", f"Virtual Villagers {game} Deaths Log", "Death ", slot)
    unacc, files = numbered_records(game_dir, "Unaccounted Villagers", f"Virtual Villagers {game} Unaccounted Villagers Log",
                                    "Unaccounted ", slot)
    label = f"{LOGS}\\Deaths and Unaccounted Villagers"
    rep.add(label, "OK", f"{len(deaths)} Death records, {len(unacc)} Unaccounted records for Save {slot}")
    global LAST_GRAVES
    LAST_GRAVES = sum(1 for d in deaths if (m := re.search(r"^  Grave: (.*)$", d, re.M)) and m.group(1).strip()
                      and not m.group(1).startswith("no grave"))
    dead = {re.search(r"Name: (.*)", d).group(1).strip() for d in deaths if re.search(r"Name: (.*)", d)}
    for u in unacc:
        m = re.search(r"Name: (.*)", u)
        if m and "Left the village" in u and m.group(1).strip() in dead:
            rep.add(label, "NOTE", f"{m.group(1).strip()} is both unaccounted for and in the Deaths log "
                                   "(a grave recorded afterwards; the Unaccounted record stays: logs are never rewritten)")
    return len(deaths)


LAST_GRAVES = 0


def village_id(header: str) -> int:
    """vv1_xc_village_id: FNV-1a of the village's Births-log header line, never 0."""
    h = 2166136261
    for c in header.encode("latin-1"):
        h = ((h ^ c) * 16777619) & 0xFFFFFFFF
    return h or 1


def check_marker(game_dir: Path, slot: int, game: int, rep: Report, village: str | None = None) -> None:
    path = game_dir / DATA / "Cross-Check" / f"Virtual Villagers {game} Cross-Check - Save {slot}.dat"
    label = f"{DATA}\\Cross-Check"
    if game != 1:
        return
    if not path.is_file():
        rep.add(label, "NOTE", "the cross-check has not run for this slot yet (it runs when the village is next played "
                               "with \"Check logs automatically\" on, or after Repair Logs)")
        return
    data = path.read_bytes()
    if len(data) != 48 or data[:4] != b"VXC1":
        rep.add(label, "UNCHECKED", "not a cross-check marker (the game sets it aside and runs the check)")
        return
    words = struct.unpack("<12I", data)
    result = {1: "clean", 2: "repaired", 3: "no Births log to check against"}.get(words[4])
    if words[1] != 1 or words[2] != 1 or words[3] != slot or result is None:
        rep.add(label, "UNCHECKED", "a marker for another game, slot or version (the game sets it aside and runs the check)")
        return
    if village is not None and words[11] != village_id(village):
        rep.add(label, "NOTE", "the marker is another village's (an earlier village in this slot): the check runs "
                               "again when this village is next checked")
        return
    rep.add(label, "OK", f"the cross-check ran for this village: {result}")


GRAVES_LOGGED_MAGIC = 0x31474356           # 'VCG1' (cod_backfill.inc LOGGED_MAGIC)
ARRIVALS_MARKER_MAGIC = 0x31414356         # 'VCA1' (arrival_backfill.h)
BIRTHS_MARKER_MAGIC = 0x31424356           # 'VCB1'


def graves_logged_path(game_dir: Path, game: int, slot: int) -> Path:
    return game_dir / DATA / "Deaths" / f"Virtual Villagers {game} Graves Logged - Save {slot}.dat"


def arrivals_marker_path(game_dir: Path, game: int, slot: int) -> Path:
    return game_dir / DATA / "Arrivals" / f"Virtual Villagers {game} Arrivals Recorded - Save {slot}.dat"


def graves_logged_problem(data: bytes, game: int) -> str | None:
    """logged_validate (native/vvfp_cause_of_death/cod_backfill.inc): None when the game reads it."""
    if len(data) < 16:
        return "shorter than its header"
    magic, version, g, count = struct.unpack_from("<4I", data, 0)
    places = 50 if game <= 2 else 500
    if magic != GRAVES_LOGGED_MAGIC or version != 1 or g != game:
        return "not a version 1 graves-logged file of this game"
    if count > places or len(data) != 16 + 8 * count:
        return f"{len(data)} bytes does not hold the {count} entries its header claims"
    previous = -1
    for i in range(count):
        place, pad, fingerprint = struct.unpack_from("<HHI", data, 16 + 8 * i)
        if place <= previous or place >= places or pad or not fingerprint:
            return f"entry {i} is out of order or malformed"
        previous = place
    return None


def backfill_marker_ok(data: bytes, magic: int, game: int, slot: int) -> bool:
    """vv_backfill_marker_present (native/shared/arrival_backfill.h): the first 16 bytes."""
    return len(data) >= 16 and struct.unpack_from("<4I", data, 0) == (magic, 1, game, slot)


def vv1_marker_ok(data: bytes, slot: int) -> bool:
    """vv1_xc_marker_state's header test (native/vv1_parentage/vv1_crosscheck.inc)."""
    return len(data) >= 48 and struct.unpack_from("<4I", data, 0) == (0x31435856, 1, 1, slot)


def check_coverage_files(game_dir: Path, slot: int, game: int, rep: Report) -> None:
    """The two files that stop the in-game backfills repeating (Repair Logs clears them)."""
    path = graves_logged_path(game_dir, game, slot)
    label = f"{DATA}\\Deaths\\{path.name}"
    if not path.is_file():
        rep.add(label, "NOTE", "no graves are recorded as already confirmed in the Deaths log yet (the game "
                               "writes this file when it next saves the village)")
    else:
        problem = graves_logged_problem(path.read_bytes(), game)
        if problem:
            rep.add(label, "UNCHECKED", f"{problem}: the game does not use it and checks every grave again")
        else:
            count = struct.unpack_from("<I", path.read_bytes(), 12)[0]
            rep.add(label, "OK", f"{count} grave(s) recorded as already confirmed in the Deaths log")
    path = arrivals_marker_path(game_dir, game, slot)
    label = f"{DATA}\\Arrivals\\{path.name}"
    if not path.is_file():
        rep.add(label, "NOTE", "the villagers' Arrived records have not been backfilled for this slot yet (the "
                               "game does it when the village is next played)")
    elif backfill_marker_ok(path.read_bytes(), ARRIVALS_MARKER_MAGIC, game, slot):
        rep.add(label, "OK", "the villagers' Arrived records were backfilled for this slot")
    else:
        rep.add(label, "UNCHECKED", "not this game's and slot's marker: the game keeps it and backfills again")


def check_approval(game_dir: Path, slot: int, game: int, rep: Report) -> None:
    """Repair Logs' approval for the slot (src/vv_log_tools.py), not yet used by the game."""
    path = game_dir / DATA / "Cross-Check" / f"Virtual Villagers {game} Repair Approved - Save {slot}.dat"
    if not path.is_file():
        return
    label = f"{DATA}\\Cross-Check"
    if path.read_bytes() == struct.pack("<4I", 0x31415256, 1, game, slot):
        rep.add(label, "NOTE", "Repair Logs approved repairing this village: the game repairs it, without asking, "
                               "the next time it is played")
    else:
        rep.add(label, "UNCHECKED", "a Repair Logs approval that is not this game's and slot's (the game ignores it)")


def detect_game(game_dir: Path, slot: int) -> int:
    for game in (2, 3, 4, 5):
        if (game_dir / f"{SAVE_STEMS[game]}{slot}.ldw").is_file():
            return game
    if (game_dir / f"Virtual Villagers{slot}.ldw").is_file():
        return 1
    raise CheckError(f"no save for slot {slot} in {game_dir}")


def check(game_dir: Path, slot: int, game: int | None = None) -> Report:
    game = game or detect_game(game_dir, slot)
    rep = Report()
    save = game_dir / f"{SAVE_STEMS[game]}{slot}.ldw"
    data = save.read_bytes()
    pop = population_for_slot(game_dir, slot)
    try:
        roster = vv1_roster(data) if game == 1 else vv25_roster(game, data, [v["name"] for v in pop or []])
    except ValueError as exc:
        rep.add(save.name, "UNCHECKED", f"the save could not be read: {exc}")
        return rep
    rep.add(save.name, "OK", f"{GAME_TITLES[game]}, Save {slot}: {len(roster)} living villagers read from the save")
    try:
        births, files = births_log(game_dir, game, slot)
    except LogUnreadable as exc:
        rep.add(f"{LOGS}\\Births and Conceptions", "UNCHECKED", f"cannot be read ({exc}): nothing that depends "
                                                                 "on it is checked, as in the game")
        births, files = BirthsLog(), []
    if births.damaged:
        rep.add(f"{LOGS}\\Births and Conceptions", "UNCHECKED",
                "a record of this village is cut short (no name, head or body): the game's check treats the log as "
                "unreadable and changes nothing, and so does this one")
        births = BirthsLog()
    rep.add(f"{LOGS}\\Births and Conceptions", "OK" if files else "NOTE",
            f"{sum(r.kind == 'birth' for r in births)} Birth and {sum(r.kind == 'conception' for r in births)} "
            f"Conception records for this village in {len(files)} file(s)")
    if game == 1:
        vv1_parentage(game_dir, slot, roster, births, rep)
    else:
        vv25_parents_vs_births(roster, births, rep, game, game_dir, slot)
    global LAST_GRAVES
    LAST_GRAVES = 0
    try:
        deaths = check_unaccounted(game_dir, slot, game, rep)
    except LogUnreadable as exc:
        rep.add(f"{LOGS}\\Deaths and Unaccounted Villagers", "UNCHECKED", f"cannot be read ({exc})")
        deaths = 0
    check_population(game_dir, slot, roster, rep)
    hist = history_last(game_dir, slot)
    check_history(game_dir, slot, roster, rep)
    elders = check_elders(game_dir, slot, game, roster, rep)
    check_statistics(game_dir, slot, game, roster, births, deaths, elders, rep)
    check_counters(game_dir, slot, game, births, LAST_GRAVES, rep)
    check_masks(game_dir, slot, game, roster, rep)
    check_titles(game_dir, slot, game, roster, hist, rep)
    check_graves(game_dir, slot, game, deaths, rep)
    check_rosters(game_dir, slot, game, roster, rep)
    check_stews(game_dir, slot, game, rep)
    check_marker(game_dir, slot, game, rep, births.village)
    check_coverage_files(game_dir, slot, game, rep)
    check_approval(game_dir, slot, game, rep)
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("folder", type=Path, help="the game's save folder: <Documents>\\LDW\\<game exe name>")
    ap.add_argument("slot", type=int, choices=range(1, 6))
    ap.add_argument("--game", type=int, choices=range(1, 6))
    args = ap.parse_args(argv)
    try:
        rep = check(args.folder, args.slot, args.game)
    except CheckError as exc:
        raise SystemExit(str(exc)) from None
    print(rep.render())
    print(f"\n{rep.wrong} confirmed wrong")
    return 1 if rep.wrong else 0


if __name__ == "__main__":
    sys.exit(main())
