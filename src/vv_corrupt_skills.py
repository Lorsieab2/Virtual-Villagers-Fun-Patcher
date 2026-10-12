"""Repair Saves & Logs: reset obviously-corrupted skill values in the save (all five games).

The owner (v1.35.70): "Can you reset obviously-corrupted skill values?"  Only a value no game can
ever hold counts -- one each game's own skill writer would never leave there:

  A New Home, The Lost Children, The Secret City: signed 32-bit integers.  The stock writers
  (0x437230, 0x445430, 0x455740) add the change, then store 100 when the sum is above 100 and 0
  when it is below 0, so every value is 0..100.
  The Tree of Life, New Believers: 32-bit floats.  The stock writers (0x46AD80, 0x475730) store
  100.0 when the sum is above 100.0 and 0.0 when it is below 0.0, so every value is 0.0..100.0.
  A NaN passes both comparisons and is never put right by the game.

What is reset: NaN or +-infinity -> 0; below 0 -> 0; above 100 -> 100.  Anything else is never
touched (exactly 0, exactly 100, and -0.0, which equals 0).

Where the save keeps them (the villager's saved entry, relative to the name; the checker's own
reading, scripts/vvfp_consistency_check.py LAYOUTS):

  A New Home       record +0x3BC (the save keeps record bytes +0x33C..+0x3D8): name +0x4C, 5 ints,
                   Parenting, Building, Farming, Healing, Research
  The Lost Children record +0x7E4 (one 0x2E0-byte window): name +0x280, 5 ints, the same order
  The Secret City   record +0xEAC (window (0xEAC,0x18) at entry +0xEC): name +0xD8, 5 ints,
                   Farming, Parenting, Healing, Research, Building
  The Tree of Life  record +0x1C5C (window (0x1C5C,0x18) at entry +0xD4): name +0xC0, 5 floats,
                   the same order
  New Believers     record +0x1C5C (writer 0x465270 copies it to entry +0xE0): name +0xC0, 6 floats,
                   the same order and Devotion

Every record the game loads is looked at: the living, the unburied dead (a body) and, in New
Believers, the Heathens (corruption is corruption; the record names them as Heathens).

survey() reads only.  reset() refuses while the game runs, backs the save folder up first (Back Up
Saves' copier, BACKUP_LABEL), copies the save into "Copies Made Before Repairs", changes only the
skill dwords it lists (every other byte stays), writes through a temporary file and reads it back
(the save is put back on a failure), and writes one "Repair <n>" record in the Repairs Made log
naming each villager, skill and old -> new value.
"""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import vv_last_names as ln
import vv_log_tools as tools
import vv_save_backup

BACKUP_LABEL = "(before resetting corrupted skills)"
COPY_SUFFIX = ".before-skill-reset"
SKILL_MAX = 100

# The skills' order in each game's record (docs/hidden-gates-all-five-games.md).
_VV12 = ("Parenting", "Building", "Farming", "Healing", "Research")
_VV345 = ("Farming", "Parenting", "Healing", "Research", "Building")
SKILL_NAMES = {1: _VV12, 2: _VV12, 3: _VV345, 4: _VV345, 5: _VV345 + ("Devotion",)}
# (offset from the name in the saved entry, float).
SKILLS = {1: (0x3BC - 0x370, False), 2: (0x280, False), 3: (0xD8, False), 4: (0xC0, True), 5: (0xC0, True)}
# The health dword (from the name): 0 or less is a body.  A New Home: record +0x344.
_HEALTH_VV1 = 0x344 - 0x370
# New Believers keeps the faction in the saved entry's header (vv_genealogy.VV5_FACTION_FROM_NAME).
_VV5_FACTION = -0x1F


class SkillResetError(Exception):
    """Nothing was changed (or the save was put back); the message says why."""


def _show(value: float | int, raw: int, is_float: bool) -> str:
    if not is_float:
        return str(value)
    if math.isnan(value):
        return f"NaN (0x{raw:08X})"
    if math.isinf(value):
        return "infinity" if value > 0 else "-infinity"
    return f"{value:.9g}"


def fixed_value(value: float | int, is_float: bool) -> float | int | None:
    """The value a corrupted skill is reset to, or None when it is a value the game can hold."""
    if is_float and (math.isnan(value) or math.isinf(value)):
        return 0.0
    if value < 0:
        return 0.0 if is_float else 0
    if value > SKILL_MAX:
        return float(SKILL_MAX) if is_float else SKILL_MAX
    return None


@dataclass
class Reset:
    """One skill of one villager to reset."""
    villager: str               # "Alapai (head 3, body 2)" and what they are
    skill: str
    offset: int                 # the dword's offset in the save
    old: float | int
    old_raw: int
    new: float | int
    is_float: bool

    def describe(self) -> str:
        return (f"{self.villager}: {self.skill} {_show(self.old, self.old_raw, self.is_float)} -> "
                f"{_show(self.new, 0, self.is_float)}")


def _who(game: int, data: bytes, at: int) -> str:
    f = ln.FIELDS[game]
    checker = tools.load_checker()
    name = ln._cstr(data, at, f.name_cap) or "(no name)"
    text = f"{name} (head {ln._i32(data, at + f.head)}, body {ln._i32(data, at + f.body)})"
    health = ln._i32(data, at + (_HEALTH_VV1 if game == 1 else checker.HEALTH[game]))
    if game == 5 and data[at + _VV5_FACTION] != 0:
        text += ", a Heathen"
    if health <= 0:
        text += ", a body not yet buried"
    return text


def survey(folder: Path, game: int, slot: int) -> list[Reset]:
    """Every corrupted skill value in the save, in the order the game loads the villagers.  Reads only."""
    data = ln.save_path(folder, game, slot).read_bytes()
    return survey_bytes(game, data)


def survey_bytes(game: int, data: bytes) -> list[Reset]:
    base, is_float = SKILLS[game]
    names = SKILL_NAMES[game]
    out: list[Reset] = []
    for at in ln._entries(game, data, bodies=True):
        for k, skill in enumerate(names):
            where = at + base + 4 * k
            raw = struct.unpack_from("<I", data, where)[0]
            value = struct.unpack_from("<f" if is_float else "<i", data, where)[0]
            new = fixed_value(value, is_float)
            if new is not None:
                out.append(Reset(_who(game, data, at), skill, where, value, raw, new, is_float))
    return out


def note(game: int, found: list[Reset], limit: int = 12) -> str:
    """Check Saves & Logs' NOTE line."""
    shown = "; ".join(r.describe() for r in found[:limit])
    more = f"; and {len(found) - limit} more" if len(found) > limit else ""
    return (f"{len(found)} skill value(s) no game can hold (NaN, infinite, below 0 or above {SKILL_MAX}): "
            f"{shown}{more}. Repair Saves & Logs, Reset corrupted skill values, resets them.")


@dataclass
class Result:
    reset: list[Reset]
    save: Path
    backup: object


def _village(folder: Path, game: int, slot: int, data: bytes) -> str | None:
    import vv_tribe_rename
    try:
        named = {g.number: g for g in vv_tribe_rename.GAMES}[game]
        name = vv_tribe_rename.save_name(named, data)
    except (KeyError, ValueError, struct.error):
        return None
    return vv_tribe_rename.village_header(name, slot) if name else None


def reset(folder: Path, game: int, slot: int, processes: vv_save_backup.ProcessController | None = None,
          now: datetime | None = None) -> Result:
    """Reset every corrupted skill value the save holds now.  Refused while the game runs; the save
    folder is backed up first; the save is written through a temporary file and read back, and put
    back as it was on any failure."""
    folder = Path(folder)
    controller = processes if processes is not None else vv_save_backup.WindowsProcesses()
    tools._refuse_if_running(folder, controller)
    save = ln.save_path(folder, game, slot)
    try:
        original = save.read_bytes()
        found = survey_bytes(game, original)
    except (struct.error, ValueError, OSError, ln.LastNamesError) as exc:
        raise SkillResetError(f"The save could not be read ({exc}); nothing was changed.") from exc
    if not found:
        raise SkillResetError("No corrupted skill value was found; nothing was changed.")
    updated = bytearray(original)
    for r in found:
        struct.pack_into("<f" if r.is_float else "<i", updated, r.offset, r.new)
    updated = bytes(updated)
    try:
        backup = vv_save_backup.copy_save_folder(folder, now or datetime.now(), suffix=BACKUP_LABEL)
    except vv_save_backup.BackupError as exc:
        raise SkillResetError(f"The backup failed, so nothing was changed. {exc}") from exc
    tools._refuse_if_running(folder, controller)
    for k in range(1, 1000):
        copy = tools.copy_before_repair(folder, save, COPY_SUFFIX + ("" if k == 1 else f"-{k}"))
        if not copy.exists():
            break
    else:
        raise SkillResetError(f"{save.name} has too many copies already; nothing was changed.")
    copy.parent.mkdir(parents=True, exist_ok=True)
    with open(copy, "xb") as handle:
        handle.write(original)
    try:
        if save.read_bytes() != original:
            raise SkillResetError(f"{save.name} changed while the skills were being reset.")
        ln._write(save, updated)
        if survey_bytes(game, save.read_bytes()):
            raise SkillResetError(f"{save.name} still holds a corrupted skill value after the reset.")
    except (OSError, SkillResetError, ln.LastNamesError) as exc:
        try:
            if save.read_bytes() != original:
                ln._write(save, original)
        except (OSError, ln.LastNamesError) as undo_exc:
            raise SkillResetError(f"Resetting the skills failed ({exc}) and the save could not be put back "
                                  f"({undo_exc}). Your backup is in {backup.backup_folder}.") from exc
        raise SkillResetError(f"Resetting the skills failed ({exc}); the save was put back as it was. "
                              f"A backup is in {backup.backup_folder}.") from exc
    try:
        note_reset(folder, game, _village(folder, game, slot, original), found, save, copy.name, backup, now, slot)
    except OSError:
        pass                                    # the reset stands; the save shows it
    return Result(found, save, backup)


def note_reset(folder: Path, game: int, village: str | None, found: list[Reset], save: Path, copy: str,
               backup, now: datetime | None = None, slot: int | None = None) -> None:
    """One "Repair <n>" record in the Repairs Made log (native/shared/repairs_log.h's shape, numbered as
    src/vv_log_tools.py repair_record_start numbers it)."""
    import vv_save_layout as layout
    header = village or "Village: (all villages in this save folder)"
    path, text = tools.repair_record_start(folder, game, header, layout.header_slot(village) or slot, now)
    text += (f"  Checked: every villager's skills in the save, for values no game can hold (NaN, infinite, "
             f"below 0 or above {SKILL_MAX})\r\n")
    for r in found:
        text += f"  Reset: {r.describe()}\r\n"
    text += f"  File: {Path(save).relative_to(folder)} -- copy kept: {copy}\r\n"
    text += f"  Backup: {Path(backup.backup_folder).name}\r\n\r\n"
    with open(path, "ab") as log:
        log.write(text.encode("latin-1", "replace"))
