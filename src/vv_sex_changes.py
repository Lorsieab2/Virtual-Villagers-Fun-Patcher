"""A villager's sex can change during play (native/shared/sex_change.h): the Custom Island Event's
`sex_change` effect and Change Appearance's "Change sex".  Nothing else on the record changes -- the name,
head and body stay, and the parents recorded on any record stay as recorded.

Each change is written, one line, to the save's own "Sex Changes - Save S.txt":

    <old>\\t<new>\\t<name>\\r\\n        old / new: M or F; the name as the record holds it (cp1252)

(older layout "<save folder>\\Virtual Villagers Fun Patcher Data\\Sex Changes\\", routed to the save's own
"Virtual Villagers Fun Patcher\\Save S\\Data\\Sex Changes\\"), and the Births and Conceptions log gets an
"Appearance changed" record with two extra lines after "New body": "  Old sex: Male" / "  New sex: Female".

THE ONE RULE (same_villager_sex): two looks at a villager agree on the sex when they say the same sex, or
when either does not say, or when the villager's name is one the change log (or an Appearance changed
record's Old sex / New sex lines) names.  A villager named there is the same villager whichever sex a
record shows -- never a death and a new arrival, never a sex to "fix".  Two candidates stay a question,
as before: this rule only lets a candidate through, it never picks one.  Nothing here writes."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

GAME_TEXT = "cp1252"
KIND = "Sex Changes"
SEX_LINE = re.compile(r"^\s*(Old|New) sex:\s*(\S.*?)\s*$", re.I)


@dataclass(frozen=True)
class SexChange:
    old: str        # "M" or "F"
    new: str
    name: str


def relative(slot: int) -> str:
    """The log's older-layout path (relative to the save folder), as vv_save_layout routes it."""
    import vv_save_layout as layout
    return f"{layout.DATA}\\{KIND}\\{KIND} - Save {int(slot)}.txt"


def letter(sex) -> str | None:
    """"M" / "F" for any way a tool writes a sex ("Male", "female", "M", ...), else None.  A number is
    not read here: each game has its own values (vv_last_names.FIELDS)."""
    if sex is None:
        return None
    text = str(sex).strip().upper()
    return text[:1] if text[:1] in ("M", "F") else None


def parse(raw: bytes) -> list[SexChange]:
    out = []
    for line in raw.decode(GAME_TEXT, errors="replace").splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        old, new, name = letter(parts[0]), letter(parts[1]), parts[2].rstrip("\r\n")
        if old and new and old != new and name and len(parts[0].strip()) == 1 and len(parts[1].strip()) == 1:
            out.append(SexChange(old, new, name))
    return out


def read(folder: Path, slot: int) -> list[SexChange]:
    """Every change the save's log holds, in order.  Both places are read (the log only grows, so the
    longer one holds the other's); an unreadable or missing log is no changes."""
    import vv_save_layout as layout
    best: list[SexChange] = []
    try:
        paths = layout.both_places(Path(folder), relative(slot))
    except OSError:
        return []
    for path in paths:
        try:
            found = parse(Path(path).read_bytes())
        except OSError:
            continue
        if len(found) > len(best):
            best = found
    return best


def changed_names(folder: Path | None, slot: int | None, extra=()) -> set[str]:
    """The names whose sex changed: the save's log, plus `extra` (names a tool found in the history
    records, history_names)."""
    out = {n for n in extra if n}
    if folder is not None and slot is not None:
        out |= {c.name for c in read(folder, slot)}
    return out


def record_name(lines: list[str]) -> str | None:
    """The villager an "Appearance changed" record's lines (the heading first) say changed sex -- its
    Old sex / New sex pair differ -- else None."""
    if not lines or lines[0].strip() != "Appearance changed":
        return None
    name, sexes = None, {}
    for line in lines[1:]:
        m = SEX_LINE.match(line)
        if m:
            sexes[m.group(1).lower()] = letter(m.group(2))
        elif line.strip().startswith("Name:") and name is None:
            name = line.split(":", 1)[1].strip()
    if name and sexes.get("old") and sexes.get("new") and sexes["old"] != sexes["new"]:
        return name
    return None


def history_names(blocks) -> set[str]:
    """The names of the Appearance changed records that carry an Old sex / New sex pair (blocks with
    `lines`, the heading first: vv_log_additions.blocks)."""
    return {n for n in (record_name(b.lines) for b in blocks) if n}


def logged_names(folder: Path, game: int, slot: int) -> set[str]:
    """changed_names with the Births and Conceptions logs' Appearance changed records of this slot's
    village read too (for a tool that does not read those records itself)."""
    import vv_log_additions as additions
    import vv_log_tools as tools
    out = changed_names(folder, slot)
    try:
        villages = additions.current_villages(Path(folder), game, slot)
        for path in tools.load_checker().births_layout_files(Path(folder), game):
            out |= history_names(b for b in additions.blocks(path) if b.of(slot, game, villages))
    except (OSError, ValueError, UnicodeError):
        pass
    return out


def is_sex_line(line: str) -> bool:
    """An Appearance changed record's "Old sex:" / "New sex:" line: kept as written, never a contradiction."""
    return bool(SEX_LINE.match(line))


def same_villager_sex(name, sex_a, sex_b, changed=frozenset()) -> bool:
    """THE rule: True when the two sexes agree (a side that does not say agrees), or when `name` (a name or
    several) is one whose sex changed."""
    a, b = letter(sex_a), letter(sex_b)
    if sex_a is None or sex_b is None or sex_a == "" or sex_b == "":
        return True
    if a is not None and b is not None:
        if a == b:
            return True
    elif str(sex_a).strip().lower() == str(sex_b).strip().lower():
        return True
    names = (name,) if isinstance(name, str) or name is None else tuple(name)
    return any(n in changed for n in names if n)
