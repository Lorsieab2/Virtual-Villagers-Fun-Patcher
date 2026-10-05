"""Cross-check every log and data file the Fun Patcher keeps for one village against its save.

usage:
    python scripts/vvfp_consistency_check.py "<Documents>\\LDW\\<game folder>" <slot> [--game N]

READ-ONLY.  Nothing is written, moved or created; the save, the logs and the .dat files are
only opened for reading.  It prints one section per file with a verdict on each line:

    OK          the file agrees with the save (and with the other files where they overlap)
    WRONG       confirmed wrong against a source of truth; "repairable" says whether the
                game's first-load cross-check repairs it (after asking the player)
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
  - Nothing outside a mask file records a mask, so masks can only be checked for form.

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
        out.append(Villager(rank=len(out), name=name, male=gender == 1, age=f(0x348), head=f(0x360),
                            body=f(0x364), skills=[f(0x3BC + 4 * k) for k in range(5)],
                            scalar=f(0x36C), due=f(0x358),
                            raw=data[base:base + VV1_STRIDE]))
    return out


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
        out.extend(_entries(data, p, lay, len(out)))
    return out


def _entries(data: bytes, p: int, lay: SaveLayout, first: int) -> list[Villager]:
    out = []
    while plausible(data, p, lay):
        skills = [(f32 if lay.skills_float else i32)(data, p + lay.skills + 4 * k) for k in range(lay.skill_count)]
        out.append(Villager(rank=first + len(out), name=cstr(data, p, lay.name_cap),
                            male=i32(data, p + lay.gender) == lay.male_value,
                            age=i32(data, p + lay.age), head=i32(data, p + lay.head), body=i32(data, p + lay.body),
                            skills=skills,
                            father=cstr(data, p + lay.father, lay.parent_cap) if lay.father is not None else "",
                            mother=cstr(data, p + lay.mother, lay.parent_cap) if lay.mother is not None else ""))
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
    kind: str                  # "birth" | "conception"
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
                                        f"mother {want[5] or '(none)'} (repairable: the first-load cross-check)")
        elif matches or not named:
            why = "the Birth records disagree" if matches else "no Birth record (a founder or a grown arrival)"
            if has:
                wrong += 1
                rep.add(label, "WRONG", f"{v.name}: recorded {now}, but {why}: set to unknown "
                                        "(repairable: the first-load cross-check)")
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


def vv25_parents_vs_births(roster: list[Villager], births: list[LogRecord], rep: Report, game: int) -> None:
    label = f"{LOGS}\\Births and Conceptions (against the save's own parent fields)"
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


def check_history(game_dir: Path, slot: int, roster: list[Villager], rep: Report) -> None:
    label = f"{LOGS}\\Tribe History (checked only: never rewritten)"
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
                               "so a heathen elder would show above as 'no open line'")
    rep.add(label, "OK", f"{len(rows)} lines, {len(open_lines)} open; {len(living_elders)} living elders in the save")
    return len(rows)


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
    buried = num("Villagers Buried")
    if buried is not None:
        rep.add(label, "OK" if buried >= deaths else "NOTE",
                f"Villagers Buried {buried} {'>=' if buried >= deaths else '<'} the {deaths} Death records in the log")
    ve = num("Village Elders")
    if ve is not None and elders is not None:
        rep.add(label, "OK" if ve == elders else "NOTE",
                f"Village Elders {ve} {'=' if ve == elders else '!='} the {elders} lines of the elders file"
                + ("" if ve == elders else " (the log is from another save than the file)"))


def check_masks(game_dir: Path, slot: int, game: int, roster: list[Villager], rep: Report) -> None:
    names = {1: f"Virtual Villagers 1 Village Masks - Save {slot}.dat",
             2: f"Virtual Villagers 2 Village Masks - Save {slot}.dat"}.get(game, f"Village Masks - Save {slot}.dat")
    candidates = [game_dir / DATA / "Village Masks" / names, game_dir / DATA / names]
    path = next((p for p in candidates if p.is_file()), None)
    label = f"{DATA}\\{names}"
    if path is None:
        rep.add(label, "NOTE", "no mask file")
        return
    data = path.read_bytes()
    magic = data[:4]
    rep.add(label, "UNCHECKED", f"{len(data)} bytes, magic {magic!r}: no save field or log records a mask, so a mask "
                                "can never be confirmed wrong; the game's load follows each mask to its villager "
                                "by the identity stored with it")


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


def check_unaccounted(game_dir: Path, slot: int, game: int, rep: Report) -> int:
    deaths, _ = numbered_records(game_dir, "Deaths", f"Virtual Villagers {game} Deaths Log", "Death ", slot)
    unacc, files = numbered_records(game_dir, "Unaccounted Villagers", f"Virtual Villagers {game} Unaccounted Villagers Log",
                                    "Unaccounted ", slot)
    label = f"{LOGS}\\Deaths and Unaccounted Villagers"
    rep.add(label, "OK", f"{len(deaths)} Death records, {len(unacc)} Unaccounted records for Save {slot}")
    dead = {re.search(r"Name: (.*)", d).group(1).strip() for d in deaths if re.search(r"Name: (.*)", d)}
    for u in unacc:
        m = re.search(r"Name: (.*)", u)
        if m and "Left the village" in u and m.group(1).strip() in dead:
            rep.add(label, "NOTE", f"{m.group(1).strip()} is both unaccounted for and in the Deaths log "
                                   "(a grave recorded afterwards; the Unaccounted record stays: logs are never rewritten)")
    return len(deaths)


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
        rep.add(label, "NOTE", "the first-load cross-check has not run for this slot yet (it runs at the next load)")
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
        rep.add(label, "NOTE", "the marker is another village's (an earlier village in this slot): the check runs at "
                               "this village's next load")
        return
    rep.add(label, "OK", f"the first-load cross-check ran for this village: {result}")


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
        vv25_parents_vs_births(roster, births, rep, game)
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
    check_masks(game_dir, slot, game, roster, rep)
    check_titles(game_dir, slot, game, roster, hist, rep)
    check_graves(game_dir, slot, game, deaths, rep)
    check_rosters(game_dir, slot, game, roster, rep)
    check_stews(game_dir, slot, game, rep)
    check_marker(game_dir, slot, game, rep, births.village)
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
