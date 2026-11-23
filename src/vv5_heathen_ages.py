"""Repair Saves & Logs: Catch up Heathen ages (New Believers only; the owner, 2026-11-22).

THE GAME.  Stock New Believers never ages a Heathen: the age credit 0x46FE90 skips a Heathen at 0x470077 (the
shown age, record +0x1B8C, stays where it was) and the life tick 0x472C90 skips one at 0x472CB7 (it copies the
age into the processed age +0x1C3C and does nothing else).  So every villager who went to the Heathens comes
back -- or stays there -- exactly as old as the day they left, and the camp's Heathens are as old as the day the
village was made.  This repair adds that frozen time to their age, where the logs and the save make it certain:

  * a Heathen now who was a villager: the time since they became a Heathen;
  * a villager now who went to the Heathens and rejoined: the time they spent as a Heathen;
  * a Heathen of the camp (never a villager): the time since the village started (the owner: "Camp
    Heathens too");
  * the puzzle Heathens (the role +0x1CFC 12 Heathen Doctor, 13 Chief, 14 Master Scientist, 15 Master
    Builder, 16 Master Farmer, 17 Mommy) are aged the same way (the owner, 2026-11-22).

The FULL time is added, even when it takes someone past old age; the preview names each one past it.

HOW THE TIME IS MEASURED (age units, 20 a year; never real dates, which pauses, speeds and the time-away cap
make meaningless).  The moments the logs know every villager's age at are
  START  the village's start: each "Arrived" record whose "How:" is "Founder" gives a founder's
         "Age at arrival" (the Cause of Death companion writes them as the village is made; the camp's
         Heathens, made with them, have one too, marked "Faction: Heathen" -- "Isolan" with Guardians of
         Isola -- and are Heathens at the start);
  each Village History snapshot ("=== Virtual Villagers 5 -- <date> ===": every villager's Age and Faction,
         Heathens included);
  NOW    the save.
The time between two neighbouring moments is how much the villagers who are believers at both aged between
them: the age difference more than half of them share (a Time Warp or Grant Youth moves only the one villager
it is cast on, and one who went to the Heathens and came back between the two is outvoted the same way).  The
time from a moment to NOW is the sum of the steps after it.  The villagers looked at are those with a sign of
the Heathens: a Heathen in the save or in any snapshot, a "Left the tribe: became a Heathen" Disappeared record,
or a "Converted from the Heathens" Arrived record.

For each villager with a sign of the Heathens, from the first moment the logs list them at (a believer then, or a
Heathen at the village's start), the frozen time is
    (time from that moment to now) - (how much older they are now than then).
It is certain only when every step of their own ages fits the time passed (never younger, never more than the
time); otherwise -- or when they are first listed as a Heathen after the start (when they became one is not
known), or the time cannot be measured -- they are listed as NOT KNOWN and nothing of theirs changes.  Once a
villager's frozen time has been added it is no longer missing, so a second run finds nothing for them.

WHAT IS WRITTEN (the saved entry, the name at entry +0x20; vv_last_names.FIELDS[5]): the age (record +0x1B8C,
name -0x10) and the processed age (record +0x1C3C, name +0xA0) both gain the same time, so the life tick never
processes the skipped years again -- the same "no double ageing" rule as the companion that ages Heathens, which
advances +0x1B8C and processes units while +0x1C3C is behind it.  A pregnancy (record +0x1C4C, name +0xB0: the
processed age at conception, 0 for none; the birth is due once the processed age passes it by 40) gains the same
time too, whoever she is (the Heathen Mommy, role 17, included): raising the processed age alone would make a
waiting birth due at once; this way the time left before the birth stays exactly as it was.  Nothing else
changes and nothing is kept outside the save; Heathens never count in the statistics, and nothing here touches
them.

OLD AGE (src/vv_game_mechanics_death.py): from 1,100 + 160 x (Medicine - 1) age units on, at each whole year of
the processed age the villager dies with a chance of 10% x the years past it.  Medicine is the save's technology
level 1 (vv_game_mechanics_vv5 LEVELS).  The preview names everyone the catch-up takes past it and their chance
at their next birthday (a Heathen only once the game ages Heathens).

SAFETY, as every Repair Saves & Logs write (src/vv_corrupt_skills.py): refused while the game runs; the save folder
is backed up first; the save is copied into "Copies Made Before Repairs"; the "Repair <n>" record is written to the
Repairs Made log; the save is written LAST (through a temporary file, read back, put back on any failure -- and a
further record then says it was not done).
"""
from __future__ import annotations

import struct
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import vv_last_names as ln
import vv_log_tools as tools
import vv_save_backup
from vv_game_text import GAME_TEXT  # the games' bytes: Windows-1252, every byte kept
from vv_log_additions import faction_side, is_heathen_faction   # "Heathen", or Guardians of Isola's "Isolan"

GAME = 5
LABEL = "Catch up Heathen ages"
BACKUP_LABEL = "(before catching up Heathen ages)"
COPY_SUFFIX = ".before-heathen-ages"
YEAR = 20                                   # age units a year
# Each villager's age is paid in whole units from their own count of time, so two moments' ages agree only to
# within a unit, and a measured time to within a unit or two: no more than this is ever taken as a change.
SLACK = 2

# Offsets from the villager's name in the saved entry (the writer 0x465270: a 0x10 header -- +1 the faction,
# +0xC the role -- then the record window (0x1B8C, 0xA8) from +0x10 and (0x1C34, 0x28) from +0xB8).
AGE = 0x1B8C - 0x1B9C                       # record +0x1B8C, the age shown
PROCESSED = 0xB8 + (0x1C3C - 0x1C34) - 0x20  # record +0x1C3C, the processed age
PREGNANCY = ln.PREGNANCY[GAME]              # record +0x1C4C, the processed age at conception
FACTION = -0x1F                             # record +0x1CEC, not 0: a Heathen
ROLE = -0x14                                # record +0x1CFC
ROLES = {12: "Heathen Doctor", 13: "Heathen Chief", 14: "Heathen Master Scientist", 15: "Heathen Master Builder",
         16: "Heathen Master Farmer", 17: "Heathen Mommy"}
# The technology levels (file offset; vv_game_mechanics_vv5.LEVELS), Medicine the second.
LEVELS, MEDICINE = 0xBC0C + 0x10, 1
OLD_AGE_BASE, OLD_AGE_STEP = 1100, 160

LEFT = "Left the tribe: became a Heathen"
CONVERTED = "Converted from the Heathens"


class HeathenAgesError(Exception):
    """Nothing was changed (or the save was put back); the message says why."""


def _i32(data, at: int) -> int:
    return struct.unpack_from("<i", data, at)[0]


def years(units: int) -> str:
    return f"{units // YEAR}" if units % YEAR == 0 else f"{units / YEAR:.2f}".rstrip("0").rstrip(".")


def old_age_threshold(medicine: int) -> int:
    return OLD_AGE_BASE + OLD_AGE_STEP * (medicine - 1)


@dataclass
class Change:
    """One villager to catch up."""
    name: str
    head: int
    body: int
    at: int                                 # the name's offset in the save
    kind: str                               # what they are, in words
    since: str                              # since when the time was measured, in words
    old_age: int
    old_processed: int
    add: int
    heathen: bool
    pregnancy: int = 0                      # the conception stamp (0: none)
    warning: str = ""

    @property
    def who(self) -> str:
        return f"{self.name} (head {self.head}, body {self.body})"

    @property
    def new_age(self) -> int:
        return self.old_age + self.add

    @property
    def new_processed(self) -> int:
        return self.old_processed + self.add

    def describe(self) -> str:
        text = (f"{self.who}, {self.kind}: age {self.old_age} -> {self.new_age} ({years(self.old_age)} -> "
                f"{years(self.new_age)} years), +{self.add} ({years(self.add)} years) {self.since}")
        if self.pregnancy:
            text += "; expecting: the time left before the birth is kept"
        return text


@dataclass
class Unknown:
    who: str
    reason: str

    def describe(self) -> str:
        return f"{self.who}: {self.reason}"


@dataclass
class Survey:
    changes: list[Change] = field(default_factory=list)
    unknown: list[Unknown] = field(default_factory=list)
    medicine: int = 1
    threshold: int = OLD_AGE_BASE
    notes: list[str] = field(default_factory=list)

    @property
    def past_old_age(self) -> list[Change]:
        return [c for c in self.changes if c.warning]

    def summary(self) -> str:
        text = f"{len(self.changes)} to catch up, {len(self.unknown)} not known (left as they are)"
        if self.past_old_age:
            text += f", {len(self.past_old_age)} taken past old age"
        return text

    def describe(self) -> str:
        """The whole preview: every change (old age -> new age), every warning and every villager left alone."""
        lines = [f"{LABEL}: the time each villager spent frozen among the Heathens (the game never ages a "
                 "Heathen) is added to their age and processed age. The full time is added, even past old age.",
                 f"Old age in this village (Medicine level {self.medicine}): from {self.threshold} age units "
                 f"({years(self.threshold)} years) on, each birthday has a 10% chance per year past it of death.",
                 ""]
        lines += self.notes + ([""] if self.notes else [])
        if self.past_old_age:
            lines.append("PAST OLD AGE AFTER THE CATCH-UP (they may die soon after the village is loaded):")
            lines += [f"  {c.who}: {c.warning}" for c in self.past_old_age]
            lines.append("")
        lines.append(f"Caught up ({len(self.changes)}):")
        lines += [f"  {c.describe()}" for c in self.changes] or ["  (none)"]
        lines.append("")
        lines.append(f"Not known, left as they are ({len(self.unknown)}):")
        lines += [f"  {u.describe()}" for u in self.unknown] or ["  (none)"]
        return "\n".join(lines)


# ------------------------------------------------------------------------------------------ the logs


@dataclass
class _Moment:
    label: str                              # in words: "the village's start", "the Village History of <date>"
    ages: dict                              # identity -> (age, heathen)
    start: bool = False


def _moments(blocks) -> tuple[list[_Moment], set, list[str]]:
    """START (when the founders are certain) and every Village History snapshot, in order; the identities with a
    record of the Heathens (Left for / Converted from); notes."""
    notes: list[str] = []
    marked: set = set()
    founders: dict = {}
    twice: set = set()
    snaps: dict[str, dict] = {}
    shared: dict[str, set] = {}
    for b in blocks:
        ident = b.identity
        if None in ident:
            continue
        head = b.heading
        if head.startswith("Disappeared") and (b.value("What happened") or "").startswith(LEFT):
            marked.add(ident)
        elif head.startswith("Arrived"):
            how = b.value("How") or ""
            if how.startswith(CONVERTED):
                marked.add(ident)
            elif how == "Founder":
                age = b.int_value("Age at arrival")
                if age is None:
                    continue
                if ident in founders:
                    twice.add(ident)
                # A Heathen of the camp, made with the founders, has a Founder record too, marked a Heathen
                # (2026-11-22): a Heathen at the village's start -- never a believer whose ageing measures time.
                founders[ident] = (age, is_heathen_faction(b.value("Faction")))
        elif head.startswith("Villager ") and b.date:
            faction = faction_side(b.value("Faction"))     # Guardians of Isola's "Isolan" is a Heathen
            age = b.int_value("Age")
            if faction is None or age is None:
                continue
            snap = snaps.setdefault(b.date, {})
            if ident in snap:
                shared.setdefault(b.date, set()).add(ident)
            snap[ident] = (age, faction == "Heathen")
    for date, idents in shared.items():
        for ident in idents:
            snaps[date].pop(ident, None)    # two villagers alike in one snapshot: neither is used
    moments = []
    if founders and not twice:
        moments.append(_Moment("the village's start", founders, start=True))
    elif twice:
        notes.append("The logs hold more than one village start (Founder records twice), so the time since the "
                     "village started is not used.")
    moments += [_Moment(f"the Village History of {date}", snaps[date]) for date in sorted(snaps)]
    return moments, marked, notes


def _step(before: dict, after: dict, alike: set) -> int | None:
    """How much the believers of both moments aged from `before` to `after`.  Each villager's age is paid in whole
    units from their own count of time (record +0x1C34), so villagers who aged alike differ by one unit at most:
    the step is taken from the two neighbouring values more than half of them share (one who went to the Heathens
    and back between the two, or had a Time Warp or Grant Youth, is outvoted), the commoner of the two."""
    votes = Counter(after[i][0] - before[i][0] for i in before
                    if i in after and i not in alike and not before[i][1] and not after[i][1])
    if not votes:
        return None
    total = sum(votes.values())
    best = max(votes, key=lambda v: (votes[v] + votes.get(v + 1, 0), votes[v]))
    if (votes[best] + votes.get(best + 1, 0)) * 2 <= total:
        return None
    value = best if votes[best] >= votes.get(best + 1, 0) else best + 1
    return value if value >= 0 else None


# ------------------------------------------------------------------------------------------ the survey


def medicine_level(data: bytes) -> int | None:
    try:
        level = _i32(data, LEVELS + 4 * MEDICINE)
    except struct.error:
        return None
    return level if level in (1, 2, 3) else None


def _warning(c: Change, threshold: int) -> str:
    if c.new_age <= threshold and c.new_processed <= threshold:
        return ""
    next_year = c.new_processed // YEAR + 1
    chance = min(100, 10 * (next_year - threshold // YEAR))
    text = (f"past old age at {years(c.new_age)} years (old age starts at {years(threshold)}): "
            f"{chance}% chance of dying at their next birthday ({next_year} years)")
    if c.heathen:
        text += ", once the game ages Heathens (the stock game never does)"
    return text


def survey_village(data: bytes, blocks) -> Survey:
    """The catch-up for the save `data`, from the person records `blocks` (vv_log_additions.person_blocks).
    Reads only."""
    medicine = medicine_level(data)
    out = Survey()
    if medicine is None:
        out.notes.append("The save's Medicine level could not be read, so old age is counted from level 1 "
                         "(the earliest).")
        medicine = 1
    out.medicine, out.threshold = medicine, old_age_threshold(medicine)
    try:
        entries = ln._entries(GAME, data)
    except ln.LastNamesError as exc:
        raise HeathenAgesError(str(exc)) from exc
    f = ln.FIELDS[GAME]
    now: dict = {}
    where: dict = {}
    alike: set = set()
    for at in entries:
        ident = (ln._cstr(data, at, f.name_cap), _i32(data, at + f.head), _i32(data, at + f.body))
        if ident in now:
            alike.add(ident)
        now[ident] = (_i32(data, at + AGE), data[at + FACTION] != 0)
        where.setdefault(ident, []).append(at)
    moments, marked, notes = _moments(blocks)
    out.notes += notes
    heathen_ever = {i for m in moments for i, (_a, h) in m.ages.items() if h} | marked
    # The time from each moment to now: the steps after it, added up (None once a step is not known).  Only
    # neighbouring moments are compared: over a long span too many villagers may have been to the Heathens.
    chain = [m.ages for m in moments] + [now]
    elapsed: list[int | None] = [None] * len(moments) + [0]
    for k in range(len(moments) - 1, -1, -1):
        step = _step(chain[k], chain[k + 1], alike) if elapsed[k + 1] is not None else None
        elapsed[k] = None if step is None else step + elapsed[k + 1]
    # A snapshot taken at the start itself (no time between): its Heathens were there at the start.
    at_start = set()
    for k, m in enumerate(moments):
        if m.start or (k and (k - 1) in at_start and elapsed[k] is not None and elapsed[k] == elapsed[k - 1]):
            at_start.add(k)
    for ident in sorted(now, key=lambda i: where[i][0]):
        age_now, heathen_now = now[ident]
        if not (heathen_now or ident in heathen_ever):
            continue
        at = where[ident][0]
        who = f"{ident[0]} (head {ident[1]}, body {ident[2]})"
        role = _i32(data, at + ROLE)
        if ident in alike:
            out.unknown.append(Unknown(who, "two villagers in the save share this name, head and body, so the logs "
                                            "cannot tell them apart"))
            continue
        seen = [(k, *moments[k].ages[ident]) for k in range(len(moments)) if ident in moments[k].ages]
        if not seen:
            out.unknown.append(Unknown(who, "not in any Village History snapshot or Founder record, so when they "
                                            "became a Heathen is not in the logs"))
            continue
        first, age0, heathen0 = seen[0]
        if heathen0 and first not in at_start:
            out.unknown.append(Unknown(who, f"first listed as a Heathen in {moments[first].label}; when they became "
                                            "one is not in the logs"))
            continue
        if elapsed[first] is None:
            out.unknown.append(Unknown(who, f"the time since {moments[first].label} cannot be measured from the logs "
                                            "(no villager who stayed a believer is listed at each step)"))
            continue
        steps = seen + [(len(moments), age_now, heathen_now)]
        if any(not 0 <= a2 - a1 <= elapsed[k1] - elapsed[k2] + SLACK
               for (k1, a1, _h1), (k2, a2, _h2) in zip(steps, steps[1:])):
            out.unknown.append(Unknown(who, "their age changed in a way the time passed cannot explain (Grant Youth, "
                                            "a Time Warp or a change by hand), so the frozen time is not certain"))
            continue
        add = elapsed[first] - (age_now - age0)
        if add <= SLACK:
            continue                         # nothing frozen, already caught up, or only the units' rounding
        former = any(not h for _k, _a, h in seen) or ident in marked
        if heathen_now:
            kind = ("a Heathen since leaving the tribe" if former else "a Heathen of the camp")
            if role in ROLES:
                kind = f"the {ROLES[role]} (a puzzle Heathen{', once a villager' if former else ' of the camp'})"
        else:
            kind = "back in the tribe after time among the Heathens"
        since = ("frozen since the village started" if heathen_now and not former
                 else "in all, frozen among the Heathens since the village started" if first in at_start
                 else f"in all, frozen among the Heathens after {moments[first].label}")
        change = Change(ident[0], ident[1], ident[2], at, kind, since, age_now, _i32(data, at + PROCESSED), add,
                        heathen_now, _i32(data, at + PREGNANCY))
        change.warning = _warning(change, out.threshold)
        out.changes.append(change)
    return out


def survey(folder: Path, slot: int) -> Survey:
    """Reads only."""
    import vv_log_additions as additions
    folder = Path(folder)
    data = ln.save_path(folder, GAME, slot).read_bytes()
    return survey_village(data, additions.person_blocks(folder, slot, GAME))


def caught_up(data: bytes, changes: list[Change]) -> bytes:
    """The save with each change made (every other byte as it was)."""
    buf = bytearray(data)
    for c in changes:
        if _i32(buf, c.at + AGE) != c.old_age or _i32(buf, c.at + PROCESSED) != c.old_processed:
            raise HeathenAgesError(f"{c.who}'s age in the save is not what the preview showed.")
        struct.pack_into("<i", buf, c.at + AGE, c.new_age)
        struct.pack_into("<i", buf, c.at + PROCESSED, c.new_processed)
        if c.pregnancy:
            struct.pack_into("<i", buf, c.at + PREGNANCY, c.pregnancy + c.add)
    return bytes(buf)


# ------------------------------------------------------------------------------------------ the repair


@dataclass
class Result:
    survey: Survey
    save: Path
    backup: object


def _village(slot: int, data: bytes) -> str | None:
    import vv_tribe_rename
    try:
        named = {g.number: g for g in vv_tribe_rename.GAMES}[GAME]
        name = vv_tribe_rename.save_name(named, data)
    except (KeyError, ValueError, struct.error):
        return None
    return vv_tribe_rename.village_header(name, slot) if name else None


def _same(a: list[Change], b: list[Change]) -> bool:
    return [(c.at, c.old_age, c.add) for c in a] == [(c.at, c.old_age, c.add) for c in b]


def catch_up(folder: Path, slot: int, processes: vv_save_backup.ProcessController | None = None,
             now: datetime | None = None, expected: Survey | None = None) -> Result:
    """Make the catch-up the survey finds now.  Refused while the game runs, when there is nothing to catch up,
    or (with `expected`, the preview the player confirmed) when the save or logs no longer give that preview."""
    import vv_log_additions as additions
    folder = Path(folder)
    controller = processes if processes is not None else vv_save_backup.WindowsProcesses()
    tools._refuse_if_running(folder, controller)
    save = ln.save_path(folder, GAME, slot)
    try:
        original = save.read_bytes()
        found = survey_village(original, additions.person_blocks(folder, slot, GAME))
    except (struct.error, ValueError, OSError, ln.LastNamesError) as exc:
        raise HeathenAgesError(f"The save or the logs could not be read ({exc}); nothing was changed.") from exc
    if not found.changes:
        raise HeathenAgesError("No Heathen's age needs catching up; nothing was changed.")
    if expected is not None and not _same(found.changes, expected.changes):
        raise HeathenAgesError("The save or the logs changed since the list was shown; nothing was changed. Open "
                               "Repair Saves & Logs again to see the new list.")
    updated = caught_up(original, found.changes)
    try:
        backup = vv_save_backup.copy_save_folder(folder, now or datetime.now(), suffix=BACKUP_LABEL)
    except vv_save_backup.BackupError as exc:
        raise HeathenAgesError(f"The backup failed, so nothing was changed. {exc}") from exc
    tools._refuse_if_running(folder, controller)
    for k in range(1, 1000):
        copy = tools.copy_before_repair(folder, save, COPY_SUFFIX + ("" if k == 1 else f"-{k}"))
        if not copy.exists():
            break
    else:
        raise HeathenAgesError(f"{save.name} has too many copies already; nothing was changed.")
    copy.parent.mkdir(parents=True, exist_ok=True)
    with open(copy, "xb") as handle:
        handle.write(original)
    village = _village(slot, original)
    # The Repairs Made record first, the save written last: a save is never changed without its record.
    try:
        note(folder, village, found, save, copy.name, backup, now, slot)
    except OSError as exc:
        raise HeathenAgesError(f"The Repairs Made log could not be written ({exc}), so the save was not changed. "
                               f"A backup is in {backup.backup_folder}.") from exc
    try:
        if save.read_bytes() != original:
            raise HeathenAgesError(f"{save.name} changed while the ages were being caught up.")
        ln._write(save, updated)
        after = save.read_bytes()
        for c in found.changes:
            if _i32(after, c.at + AGE) != c.new_age or _i32(after, c.at + PROCESSED) != c.new_processed:
                raise HeathenAgesError(f"{save.name} does not show {c.who}'s new age after the write.")
    except (OSError, HeathenAgesError, ln.LastNamesError) as exc:
        try:
            if save.read_bytes() != original:
                ln._write(save, original)
        except (OSError, ln.LastNamesError) as undo_exc:
            _not_done(folder, village, slot, now, f"{exc}; the save could not be put back ({undo_exc})")
            raise HeathenAgesError(f"Catching up the Heathen ages failed ({exc}) and the save could not be put "
                                   f"back ({undo_exc}). Your backup is in {backup.backup_folder}.") from exc
        _not_done(folder, village, slot, now, f"{exc}; the save was put back as it was")
        raise HeathenAgesError(f"Catching up the Heathen ages failed ({exc}); the save was put back as it was. "
                               f"A backup is in {backup.backup_folder}.") from exc
    return Result(found, save, backup)


def note(folder: Path, village: str | None, found: Survey, save: Path, copy: str, backup,
         now: datetime | None = None, slot: int | None = None) -> None:
    """One "Repair <n>" record in the Repairs Made log (native/shared/repairs_log.h's shape)."""
    import vv_save_layout as layout
    header = village or "Village: (all villages in this save folder)"
    path, text = tools.repair_record_start(folder, GAME, header, layout.header_slot(village) or slot, now)
    text += (f"  Checked: {LABEL}: the time each villager spent frozen among the Heathens, from the Village "
             "History snapshots, the Founder records and the save\r\n")
    for c in found.changes:
        text += f"  Aged: {c.describe()}\r\n"
    for c in found.past_old_age:
        text += f"  Past old age: {c.who}: {c.warning}\r\n"
    for u in found.unknown:
        text += f"  Not known, left as they are: {u.describe()}\r\n"
    text += f"  File: {Path(save).relative_to(folder)} -- copy kept: {copy}\r\n"
    text += f"  Backup: {Path(backup.backup_folder).name}\r\n\r\n"
    with open(path, "ab") as log:
        log.write(text.encode(GAME_TEXT, "replace"))


def _not_done(folder: Path, village: str | None, slot: int, now: datetime | None, why: str) -> None:
    """A further record when the save write failed after its record was written: the record above is undone."""
    import vv_save_layout as layout
    header = village or "Village: (all villages in this save folder)"
    try:
        path, text = tools.repair_record_start(folder, GAME, header, layout.header_slot(village) or slot, now)
        text += f"  Not done: the {LABEL} in the record before this one: {why}\r\n\r\n"
        with open(path, "ab") as log:
            log.write(text.encode(GAME_TEXT, "replace"))
    except OSError:
        pass
