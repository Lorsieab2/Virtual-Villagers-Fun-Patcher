"""Repair Saves & Logs: bring A New Home's Golden Child back (the owner, 2026-10-24, option 3).

The Golden Child can die or vanish in the original game (an island event picks him like anyone: see
the Golden Child group of the Game Mechanics window), and the game never makes another, so his puzzles
(the cave, the butterflies) can then never be done.  The owner's rule: revive him the simplest way --
health above 0, still five years old -- remove his grave, and add a record saying he returned (the logs
are append-only: nothing already written is changed); only while his record slot has not been reused.

WHERE HE IS.  A New Home saves its villager records +0x33C..+0x3D8 (0x9C bytes each, 256 of them,
from save offset 0x184; scripts/vvfp_consistency_check.py VV1_BLOCK0 / VV1_STRIDE / VV1_BASE).  The
game loads them in order and stops at the first whose present byte (+0x3D4) is not 1; when a villager
is removed the game closes the list up, so the records after that gap are stale copies, never loaded.
He is the record whose family number (+0x36C) is 199 (0xC7: 0x41FBDC, 0x42E5A4, 0x438982); the save's
Golden Child byte (state +0xA008, written only at his birth, 0x424289) says the village has had one.

  * A body (in the loaded list, health +0x344 at 0 or below): his record is there -- revived in place.
  * Gone (buried or vanished): his record survives only as the first stale copy, the one at the gap,
    which nothing has written over since; that one is made present again.  Anywhere else his record
    has been reused (closed up over, or written by a newer villager), and nothing is done.

WHAT IS WRITTEN.  Health 100 (his health at birth, 0x43C7AF..0x43C80C: he never regains any), age and
processed age 100 (five: the age lock 0x42EB70 holds them there), not sick (+0x354), and present (+0x3D4)
when he was gone -- then the stale copy after him is flagged not present, so the game's load stops after
him exactly as it stopped before him (no stale copy comes back with him).  His grave, if the save has one (A New Home's graves: save 0xA320, 50 x 0x2C, name
+0, age +0x24 in age units), is emptied: a grave of age 0 is an empty place the game's next burial
reuses.  A "Returned to life" record is appended to the slot's Deaths and Disappearances log, under the
village's header, and a "Repair <n>" record to the Repairs Made log.

Safety, as every Repair Saves & Logs write (src/vv_corrupt_skills.py): refused while the game runs; the
save folder is backed up first; the save is copied into "Copies Made Before Repairs", written through a
temporary file and read back, and put back on any failure.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import vv_last_names as ln
import vv_log_tools as tools
import vv_save_backup

GAME = 1
BACKUP_LABEL = "(before reviving the Golden Child)"
COPY_SUFFIX = ".before-golden-child-revive"
HEADING = "Returned to life"

BLOCK0, STRIDE, BASE, RECORDS = 0x184, 0x9C, 0x33C, 256
PRESENT, HEALTH, AGE, PROCESSED, SICK, FAMILY, NAME, SEX, HEAD, BODY = (
    0x3D4, 0x344, 0x348, 0x34C, 0x354, 0x36C, 0x370, 0x350, 0x360, 0x364)
GOLDEN_FAMILY = 199
GOLDEN_BYTE = 0xA008 + 4                    # file offset (state + 4)
GRAVES, GRAVE_PLACES, GRAVE_STRIDE, GRAVE_NAME_CAP, GRAVE_AGE, GRAVE_SKILL = 0xA320, 50, 0x2C, 0x1C, 0x24, 0x1C
FIVE = 100                                  # age units: 5 villager years
REVIVED_HEALTH = 100


class ReviveError(Exception):
    """Nothing was changed (or the save was put back); the message says why."""


def _i32(data, at: int) -> int:
    return struct.unpack_from("<i", data, at)[0]


def _rel(i: int, offset: int) -> int:
    return BLOCK0 + i * STRIDE + offset - BASE


def _name(data, at: int, cap: int) -> str:
    return bytes(data[at:at + cap]).split(b"\0", 1)[0].decode("latin-1")


@dataclass
class Survey:
    """What Repair can do for this save's Golden Child: `state` is "none" (the village never had one),
    "alive", "body" or "gone" (revivable), or "reused" (his record is no longer there)."""
    state: str
    index: int | None = None                # his record's place
    name: str = ""
    health: int = 0
    graves: tuple = ()                      # the save offsets of his graves (by name, age five)

    @property
    def revivable(self) -> bool:
        return self.state in ("body", "gone")

    def describe(self) -> str:
        who = self.name or "The Golden Child"
        if self.state == "none":
            return "This village has never had a Golden Child."
        if self.state == "alive":
            return f"{who}, the Golden Child, is alive (health {self.health}): nothing to do."
        if self.state == "reused":
            return ("The Golden Child is gone and his record has been reused by the game, so he cannot be "
                    "brought back.")
        grave = " and his grave removed" if self.graves else ""
        where = "his body is still in the village" if self.state == "body" else "his record is still in the save"
        return (f"{who}, the Golden Child, can be brought back ({where}): health {REVIVED_HEALTH}, still five years "
                f"old{grave}, and a \"{HEADING}\" record added.")


def survey_bytes(data: bytes) -> Survey:
    if len(data) < GRAVES + GRAVE_PLACES * GRAVE_STRIDE or len(data) < _rel(RECORDS, 0):
        raise ReviveError("This is not an A New Home save.")
    if data[GOLDEN_BYTE] == 0:
        return Survey("none")
    loaded = 0
    while loaded < RECORDS and data[_rel(loaded, PRESENT)] == 1:
        loaded += 1
    for i in range(loaded):
        if _i32(data, _rel(i, FAMILY)) == GOLDEN_FAMILY:
            health = _i32(data, _rel(i, HEALTH))
            name = _name(data, _rel(i, NAME), 0x1C)
            # A body is not buried yet, so it has no grave: no grave is ever touched for one.
            return Survey("alive" if health > 0 else "body", i, name, health, ())
    if loaded < RECORDS and _i32(data, _rel(loaded, FAMILY)) == GOLDEN_FAMILY \
            and _name(data, _rel(loaded, NAME), 0x1C):
        name = _name(data, _rel(loaded, NAME), 0x1C)
        return Survey("gone", loaded, name, _i32(data, _rel(loaded, HEALTH)), _graves(data, name))
    return Survey("reused")


def _graves(data, name: str) -> tuple:
    """His grave, only when it is certainly his: his name, age 100 (five) and a best skill of 100 -- every
    skill of his is 100 (0x43C7AF..0x43C80C), which a five-year-old namesake reaches only through an event.
    None such, or more than one, and no grave is touched (Codex, #625: never erase a namesake's grave on a
    guess)."""
    out = []
    for place in range(GRAVE_PLACES):
        at = GRAVES + place * GRAVE_STRIDE
        if name and _name(data, at, GRAVE_NAME_CAP) == name and _i32(data, at + GRAVE_AGE) == FIVE \
                and _i32(data, at + GRAVE_SKILL) == 100:
            out.append(at)
    return tuple(out) if len(out) == 1 else ()


def survey(folder: Path, slot: int) -> Survey:
    """Reads only."""
    return survey_bytes(ln.save_path(folder, GAME, slot).read_bytes())


def revived(data: bytes, found: Survey) -> bytes:
    """The save with him brought back (every other byte as it was)."""
    buf = bytearray(data)
    i = found.index
    struct.pack_into("<i", buf, _rel(i, HEALTH), REVIVED_HEALTH)
    struct.pack_into("<i", buf, _rel(i, AGE), FIVE)
    struct.pack_into("<i", buf, _rel(i, PROCESSED), FIVE)
    struct.pack_into("<i", buf, _rel(i, SICK), 0)
    if found.state == "gone":
        buf[_rel(i, PRESENT)] = 1
        # The stale copies after him stay unloaded, as they are now: the game would load on past him into
        # any of them still flagged present (the loader stops only at a record not flagged 1).
        if i + 1 < RECORDS:
            buf[_rel(i + 1, PRESENT)] = 0
    for at in found.graves:
        buf[at:at + GRAVE_STRIDE] = bytes(GRAVE_STRIDE)
    return bytes(buf)


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


def returned_record(data: bytes, found: Survey) -> str:
    i = found.index
    sex = "Male" if _i32(data, _rel(i, SEX)) == 1 else "Female"
    return "\n".join([
        HEADING,
        f"  Name: {found.name}",
        "  Special villager: Golden Child",
        f"  Age: {FIVE} (5 years)",
        f"  Sex: {sex}",
        f"  How: brought back by Repair Saves & Logs ({'his body' if found.state == 'body' else 'his record'} "
        f"was still in the save): health {REVIVED_HEALTH}, still five years old"
        + ("; his grave was removed" if found.graves else ""),
        f"  Head: {_i32(data, _rel(i, HEAD))}",
        f"  Body: {_i32(data, _rel(i, BODY))}",
    ]) + "\n"


def _append_returned(folder: Path, slot: int, village: str | None, text: str) -> Path:
    import vv_log_additions as additions
    import vv_save_layout as layout
    stem = f"Virtual Villagers {GAME} Deaths Log"
    target = layout.append_target(folder, layout.DEATHS_LOGS, stem, slot, "Death ")
    villages = additions.current_villages(folder, GAME, slot)
    _anchor, lead = additions._append_point(target, slot, GAME, villages, village)
    newline = "\r\n"
    if target.exists():
        head = target.read_bytes()[:4096]
        newline = "\r\n" if b"\r\n" in head or b"\n" not in head else "\n"
    target.parent.mkdir(parents=True, exist_ok=True)
    body = (lead + text + "\n").replace("\r\n", "\n").replace("\n", newline)
    with open(target, "ab") as log:
        log.write(body.encode("latin-1", "replace"))
    return target


def revive(folder: Path, slot: int, processes: vv_save_backup.ProcessController | None = None,
           now: datetime | None = None) -> Result:
    """Bring the Golden Child back.  Refused while the game runs or when he cannot be (see Survey)."""
    folder = Path(folder)
    controller = processes if processes is not None else vv_save_backup.WindowsProcesses()
    tools._refuse_if_running(folder, controller)
    save = ln.save_path(folder, GAME, slot)
    try:
        original = save.read_bytes()
        found = survey_bytes(original)
    except (struct.error, OSError) as exc:
        raise ReviveError(f"The save could not be read ({exc}); nothing was changed.") from exc
    if not found.revivable:
        raise ReviveError(found.describe() + " Nothing was changed.")
    updated = revived(original, found)
    try:
        backup = vv_save_backup.copy_save_folder(folder, now or datetime.now(), suffix=BACKUP_LABEL)
    except vv_save_backup.BackupError as exc:
        raise ReviveError(f"The backup failed, so nothing was changed. {exc}") from exc
    tools._refuse_if_running(folder, controller)
    for k in range(1, 1000):
        copy = tools.copy_before_repair(folder, save, COPY_SUFFIX + ("" if k == 1 else f"-{k}"))
        if not copy.exists():
            break
    else:
        raise ReviveError(f"{save.name} has too many copies already; nothing was changed.")
    copy.parent.mkdir(parents=True, exist_ok=True)
    with open(copy, "xb") as handle:
        handle.write(original)
    try:
        if save.read_bytes() != original:
            raise ReviveError(f"{save.name} changed while the Golden Child was being brought back.")
        ln._write(save, updated)
        if survey_bytes(save.read_bytes()).state != "alive":
            raise ReviveError(f"{save.name} does not show the Golden Child alive after the write.")
    except (OSError, ReviveError, ln.LastNamesError) as exc:
        try:
            if save.read_bytes() != original:
                ln._write(save, original)
        except (OSError, ln.LastNamesError) as undo_exc:
            raise ReviveError(f"Bringing the Golden Child back failed ({exc}) and the save could not be put "
                              f"back ({undo_exc}). Your backup is in {backup.backup_folder}.") from exc
        raise ReviveError(f"Bringing the Golden Child back failed ({exc}); the save was put back as it was. "
                          f"A backup is in {backup.backup_folder}.") from exc
    village = _village(slot, original)
    try:
        _append_returned(folder, slot, village, returned_record(original, found))
    except OSError:
        pass                                    # the revive stands; the save shows it
    try:
        _note(folder, village, found, save, copy.name, backup, now, slot)
    except OSError:
        pass
    return Result(found, save, backup)


def _note(folder: Path, village: str | None, found: Survey, save: Path, copy: str, backup,
          now: datetime | None, slot: int) -> None:
    import vv_save_layout as layout
    header = village or "Village: (all villages in this save folder)"
    path, text = tools.repair_record_start(folder, GAME, header, layout.header_slot(village) or slot, now)
    text += f"  Revived: {found.name}, the Golden Child (record {found.index + 1}, {found.state}): health " \
            f"{REVIVED_HEALTH}, age {FIVE} (5 years)" + ("; his grave emptied" if found.graves else "") + "\r\n"
    text += f"  File: {Path(save).relative_to(folder)} -- copy kept: {copy}\r\n"
    text += f"  Backup: {Path(backup.backup_folder).name}\r\n\r\n"
    with open(path, "ab") as log:
        log.write(text.encode("latin-1", "replace"))
