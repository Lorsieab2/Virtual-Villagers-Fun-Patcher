"""Backups... (the owner, 2026-11-09: "ALSO SHOW VITAL STATISTICS FOR EACH BACKUP IN A WINDOW!!! POPULATION FOOD
TECH POINTS LAST SAVED TIME ETC LAST PLAYED TIME ETC"): the vital statistics of every slot save in one backup, all
five games.  Read-only: nothing here writes, moves or makes a file.

Every value comes from a reader the patcher already has -- no offset of its own:

  tribe name          vv_save_backup.read_village_name (the Restore Saves list's)
  population          vv_game_mechanics_life.people / tribe (the Game Mechanics page's Vital statistics): living
                      villagers; in New Believers believers only, the Heathens outside the tribe apart; babies on
                      the way counted as the game counts them (pending babies count toward the population)
  food, tech points   the Context each game's Game Mechanics module builds (vv_game_mechanics_life.save_context)
  last played         that Context's last moment: the save's own last-tick time (A New Home: the clock's saved
                      moment), the moment time away counts from
  technology levels   vv_game_mechanics_tech_time.techs
  difficulty          vv_game_mechanics_life.difficulty
  game speed, Paused  vv_save_backup.save_speed / speed_words (Paused alone, as Repair Saves & Logs shows it)
  saved               the save file's own modified time (a backup keeps each file's time)
  real hours played   the Village Statistics log in the backup (vv_game_mechanics_counts.statistics_log)
  the backup          vv_save_backup.list_backups: its date and time, label, files and size

A value that cannot be read is None and is shown as UNKNOWN, never guessed.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

import vv_game_mechanics as gm
import vv_save_backup
import vv_tribe_rename

UNKNOWN = "unknown"
SLOTS = range(1, 6)
# A last-tick time before 2000 or far past now is no time the game wrote: shown as unknown.
_EARLIEST = 946_684_800


@dataclass
class SlotDetails:
    slot: int
    save: Path
    tribe: str | None = None
    villagers: int | None = None        # living villagers in the tribe (New Believers: believers only)
    babies: int | None = None           # babies on the way
    heathens: int | None = None         # New Believers' Heathens outside the tribe (None in the other games)
    food: int | None = None
    tech_points: int | None = None
    techs: dict[str, int] | None = None
    difficulty: str | None = None
    speed: str | None = None            # "Normal", "Fast", "Slow" or "Paused"
    saved: float | None = None          # the save file's own modified time
    last_tick: float | None = None      # the save's own last-tick time (last played)
    hours_played: int | None = None     # Village Statistics' Real Hours Played
    notes: list[str] = field(default_factory=list)

    @property
    def population(self) -> int | None:
        if self.villagers is None:
            return None
        return self.villagers + (self.babies or 0)


@dataclass
class BackupDetails:
    info: vv_save_backup.BackupInfo
    slots: list[SlotDetails]


def _plausible(moment: float | None, now: float) -> float | None:
    if moment is None or not _EARLIEST <= moment <= now + gm.TEN_YEARS:
        return None
    return float(moment)


def read_slot(game: int, folder: Path, slot: int, now: float | None = None) -> SlotDetails:
    """One slot save's vital statistics, read from ``folder`` (a backup, or any save folder).  Reads only."""
    import vv_game_mechanics_counts as counts
    import vv_game_mechanics_life as life
    import vv_game_mechanics_tech_time as tech_time

    now = time.time() if now is None else now
    saves = next(item for item in vv_tribe_rename.GAMES if item.number == game)
    path = saves.save_path(Path(folder), slot)
    out = SlotDetails(slot, path)
    try:
        out.saved = path.stat().st_mtime
        data = path.read_bytes()
    except OSError as exc:
        out.notes.append(f"The save could not be read ({exc.strerror or exc}).")
        return out
    out.tribe = vv_save_backup.read_village_name(game, path)
    found = vv_save_backup.save_speed(game, data)
    out.speed = vv_save_backup.speed_words(found[1]) if found is not None else None
    if out.tribe is None and found is None:
        out.notes.append(f"{path.name} is not a save of this game that can be read.")
        return out
    village = gm.Village(Path(folder), game, slot, path, data, None, now)
    try:
        everyone = life.people(village)
    except Exception:  # noqa: BLE001 -- an unreadable table is an unknown population
        everyone = None
    if everyone is not None:
        members = life.tribe(everyone)
        out.villagers = len(members)
        out.babies = sum(p.babies for p in members if p.carrying)
        if game == 5:
            out.heathens = len(everyone) - len(members)
    try:
        ctx = life.save_context(village)
    except Exception:  # noqa: BLE001 -- a save its module cannot read: those values are unknown
        ctx = None
    if ctx is not None:
        out.food = ctx.food
        out.tech_points = ctx.tech
        out.last_tick = _plausible(ctx.last, now)
    try:
        levels = tech_time.techs(game, data)
    except Exception:  # noqa: BLE001
        levels = None
    if levels and all(0 <= value <= 10 for value in levels.values()):
        out.techs = levels
    try:
        level = life.difficulty(game, data)
    except Exception:  # noqa: BLE001
        level = None
    out.difficulty = life.DIFFICULTY.get(level) if level is not None else None
    try:
        log = counts.statistics_log(village)
    except Exception:  # noqa: BLE001
        log = None
    if log is not None and "Real Hours Played" in log.rows:
        out.hours_played = log.rows["Real Hours Played"][0]
    return out


def slot_numbers(game: int, folder: Path) -> list[int]:
    """The slots whose own save ("<base><1-5>.ldw") is in ``folder``."""
    saves = next(item for item in vv_tribe_rename.GAMES if item.number == game)
    return [slot for slot in SLOTS if saves.save_path(Path(folder), slot).is_file()]


def read_backup(game: int, info: vv_save_backup.BackupInfo, now: float | None = None) -> BackupDetails:
    """Every slot save in one backup (vv_save_backup.list_backups' BackupInfo)."""
    return BackupDetails(info, [read_slot(game, info.path, slot, now) for slot in slot_numbers(game, info.path)])


# ---------------------------------------------------------------------------
# Words
# ---------------------------------------------------------------------------


def _n(value: int | None) -> str:
    return UNKNOWN if value is None else f"{value:,}"


def _moment(value: float | None) -> str:
    return UNKNOWN if value is None else gm.when(value)


def backup_label(info: vv_save_backup.BackupInfo) -> str:
    """The backup's date and time and its label: "9 November 2026, 2:03 PM (before restore)"."""
    stamp = info.when
    hour = stamp.hour % 12 or 12
    words = (f"{stamp.day} {gm._MONTHS[stamp.month - 1]} {stamp.year}, {hour}:{stamp.minute:02d}:{stamp.second:02d} "
             f"{'AM' if stamp.hour < 12 else 'PM'}")
    return f"{words} {info.suffix}".strip()


def summary(info: vv_save_backup.BackupInfo) -> str:
    """One line for the list of backups: when, which slots and tribes, files and size."""
    villages = ", ".join(f"Save {slot}: {name or '(no name)'}" for slot, name in info.villages.items())
    return (f"{backup_label(info)}   {villages or 'no village saves'}   "
            f"{info.file_count} files, {vv_save_backup.describe_size(info.size)}")


def population_words(slot: SlotDetails) -> str:
    if slot.villagers is None:
        return UNKNOWN
    words = f"{slot.villagers:,} villager{'s' if slot.villagers != 1 else ''}"
    if slot.babies:
        words += (f" and {slot.babies:,} bab{'ies' if slot.babies != 1 else 'y'} on the way "
                  f"({slot.population:,} in all, as the game counts it)")
    if slot.heathens is not None:
        words += f"; Heathens outside the tribe: {slot.heathens:,} (never counted)"
    return words


def slot_lines(slot: SlotDetails) -> list[str]:
    """The lines shown for one slot save."""
    lines = [f"Save {slot.slot}: {slot.tribe if slot.tribe else UNKNOWN}"]
    lines += [f"  {note}" for note in slot.notes]
    lines.append(f"  Population: {population_words(slot)}")
    lines.append(f"  Food in storage: {_n(slot.food)}")
    lines.append(f"  Tech points: {_n(slot.tech_points)}")
    lines.append("  Technology levels: " + (", ".join(f"{name} {level}" for name, level in slot.techs.items())
                                            if slot.techs else UNKNOWN))
    lines.append(f"  Game speed: {slot.speed or UNKNOWN}; difficulty: {slot.difficulty or UNKNOWN}")
    lines.append(f"  Last saved: {_moment(slot.saved)} (the save file's own time)")
    lines.append(f"  Last played: {_moment(slot.last_tick)} (the save's own last-tick time, real time)")
    lines.append(f"  Real hours played: {_n(slot.hours_played)}"
                 + (" (the Village Statistics log in this backup)" if slot.hours_played is not None else ""))
    return lines


def backup_lines(details: BackupDetails) -> list[str]:
    """The lines shown for one backup: its date, folder, size and slots, then each slot."""
    info = details.info
    held = ", ".join(str(slot.slot) for slot in details.slots) or "none"
    lines = [f"Backup: {backup_label(info)}",
             f"  Folder: {info.path}",
             f"  Size: {vv_save_backup.describe_size(info.size)} in {info.file_count:,} files",
             f"  Save slots held: {held}"]
    for slot in details.slots:
        lines.append("")
        lines += slot_lines(slot)
    if not details.slots:
        lines += ["", "This backup holds no slot save."]
    return lines

