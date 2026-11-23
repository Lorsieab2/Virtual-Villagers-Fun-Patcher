"""Delete Player Slot: send every file tied to one save slot to the Windows Recycle Bin.

The owner (2026-11-23): the Copy Player Slot window's "Delete" choice sends EVERY file linked to a save slot to
the Recycle Bin -- "files linked to save slots = logs, sidecars, backups, family tree files (NOT images) etc".
Nothing is ever deleted for good: every file goes through the Windows shell's Recycle Bin
(vv_translations.recycle: SHFileOperationW with FOF_ALLOWUNDO, refused when the drive has no Recycle Bin), so
the player can put any of it back from there.  No new backup is made (the owner: the Recycle Bin is the way
back).

What goes (Move Player Slot's discovery, src/vv_move_slot.py slot_everything, so the two never disagree)
    * The slot save "<stem><S>.ldw", the game's older generations "<stem>2<S>.ldw" / "<stem>4<S>.ldw", the
      save's own patcher folders ("Virtual Villagers Fun Patcher\\Save <S>", "...Logs\\Save <S>") and every
      patcher file named for the slot -- logs, every data / sidecar file, repair copies, saved family trees and
      the family tree reports' text and pages.
    * The slot's repair copies whose short name lost the slot (vv_repair_copies SHORT_MAX), found by the file
      they are a copy of in "Copies Index.txt"; each index then loses the lines of the copies that went.
    * In every whole-folder backup in "Backups": only that slot's files, found the same way inside the backup
      (its Long Paths folder too), so every other slot of every backup can still be restored.  And the slot's
      own "Replaced by copy/move ... - Save <S> - ..." folders.
    NOT recycled: pictures (.png, .jpg, .jpeg, .bmp, .gif) -- the owner: "NOT images".  They stay where they
    are and the preview lists them as kept.

Order and safety
    * Refused while the game runs.  The player sees every file first (`Plan.preview`); what they confirmed is
      fingerprinted (each file's size and time, the slot list's bytes), and anything changed since refuses.
    * The save folder's own files go first, then each backup's, then the set-aside folders.  If Windows
      refuses a batch, everything stops and the result says what went and what did not.
    * The slot list "<stem>0.ldw" is written LAST ("NEW PLAYER", not in use) -- and also after a failure once
      the slot's save is gone, so the slot is never listed with no save behind it.
    * The slot's folders left empty are removed (empty folders only).
    * One line in the Backups index records the delete (kind "deleted", never a backup Restore Saves offers).
"""
from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import vv_copy_slot as cs
import vv_long_paths as lp
import vv_move_slot as ms
import vv_repair_copies as repair_copies
import vv_save_backup
import vv_tribe_rename as rename

TITLE = "Delete Player Slot"
PICTURES = (".png", ".jpg", ".jpeg", ".bmp", ".gif")
KIND_DELETED = "deleted"
BATCH = 200                      # files per Recycle Bin call


class DeleteError(cs.CopyError):
    """A delete that was refused or failed, with a reason a player can read."""


class GameRunning(DeleteError):
    """The game that uses this save folder is running."""


def is_picture(path: Path) -> bool:
    return Path(path).name.casefold().endswith(PICTURES)


@dataclass
class Group:
    """Files recycled together: the save folder's own, one backup's, or one set-aside folder's."""
    where: str                                   # "" the save folder; else "Backups\\<folder>"
    files: list[Path] = field(default_factory=list)
    pictures: list[Path] = field(default_factory=list)
    indexes: dict = field(default_factory=dict)  # Copies Index path -> its bytes without the recycled copies
    folders: list[Path] = field(default_factory=list)   # the slot's folders to remove once empty
    aside: Path | None = None                    # a whole set-aside folder (its Backups index line forgotten)


@dataclass
class Plan:
    game: rename.GameSaves
    folder: Path
    slot: int
    name: str | None                             # the village (None: its save cannot be read)
    index_before: bytes | None
    index_after: bytes | None
    groups: list[Group] = field(default_factory=list)
    fingerprints: tuple = ()

    @property
    def files(self) -> list[Path]:
        return [p for g in self.groups for p in g.files]

    @property
    def pictures(self) -> list[Path]:
        return [p for g in self.groups for p in g.pictures]

    def signature(self) -> tuple:
        return (tuple(sorted(str(p).casefold() for p in self.files)), self.fingerprints)

    def preview(self) -> list[str]:
        rel = lambda p: str(Path(p).relative_to(self.folder))            # noqa: E731
        lines = []
        for group in self.groups:
            lines += [f"Recycled:  {rel(p)}" for p in group.files]
        lines += [f"Kept (pictures):  {rel(p)}" for p in self.pictures]
        return lines


# ---------------------------------------------------------------------------
# What goes
# ---------------------------------------------------------------------------


def _slot_of_relative(game: rename.GameSaves, relative: Path, slot: int) -> bool:
    """Whether a file at ``relative`` in a save folder is slot ``slot``'s, by its path alone (a backup's long
    file, kept under a short name: slot_everything cannot walk to it)."""
    parts = relative.parts
    if not parts:
        return False
    if len(parts) == 1:
        here = Path()
        names = [game.save_path(here, slot).name] + [game.generation_path(here, g, slot).name
                                                      for g in rename.GENERATIONS]
        if parts[0].casefold() in (n.casefold() for n in names):
            return True
        legacy = cs._LEGACY_TOP.match(parts[0])
        top = cs._TOP_STATISTICS.match(parts[0])
        return bool((legacy and int(legacy.group(2)) == slot) or (top and int(top.group(1)) == slot))
    top = parts[0].casefold()
    if top in (cs.SAVES.casefold(), cs.LOGS.casefold()) and parts[1].casefold() == f"save {slot}":
        return True
    if top in (cs.SAVES.casefold(), cs.LOGS.casefold()) and re.fullmatch(r"(?i)save [1-5]", parts[1]):
        return False
    if top not in (cs.SAVES.casefold(), cs.DATA.casefold(), cs.LOGS.casefold(), cs.TREES.casefold(),
                   cs.LEGACY_LOGS.casefold()):
        return False
    if cs._name_game(parts[-1]) not in (0, game.number):
        return False
    trees = top == cs.TREES.casefold() or (top == cs.LOGS.casefold() and parts[1].casefold() == "genealogy")
    return cs._name_slot(parts[-1], trees=trees) == slot


def _copies_indexes(root: Path) -> list[Path]:
    return [p / repair_copies.INDEX for p in repair_copies._all_copies_folders(root)
            if lp.is_file(p / repair_copies.INDEX)]


def _discover(game: rename.GameSaves, root: Path, slot: int, where: str) -> Group:
    """Slot ``slot``'s files in the save folder (or the backup) ``root``."""
    group = Group(where)
    found = {str(p).casefold(): p for p in ms.slot_everything(game, root, slot)}
    if where:
        long = vv_save_backup.long_places(root)
        for relative, stored in long.items():
            if _slot_of_relative(game, relative, slot):
                found.setdefault(str(stored).casefold(), stored)
    relatives = {str(p.relative_to(root)).casefold() for p in found.values()
                 if vv_save_backup.LONG_PATHS not in p.relative_to(root).parts}
    relatives |= {str(r).casefold() for r, s in (vv_save_backup.long_places(root).items() if where else ())
                  if str(s).casefold() in found}
    # A repair copy whose short name lost the slot: found by the file it is a copy of.
    for index in _copies_indexes(root):
        for kept in repair_copies.entries(index.parent):
            if kept.original.casefold() in relatives and lp.is_file(kept.copy):
                found.setdefault(str(kept.copy).casefold(), kept.copy)
    for path in sorted(found.values(), key=lambda p: str(p).casefold()):
        (group.pictures if is_picture(path) else group.files).append(path)
    going = {str(p).casefold() for p in group.files}
    for index in _copies_indexes(root):
        if str(index).casefold() in going:
            continue                                     # the slot's own index goes with its folder
        raw = lp.read_bytes(index)
        kept_lines = []
        for line in raw.splitlines(keepends=True):
            name = line.decode("utf-8", "replace").split("\t", 1)[0]
            if not line.startswith(b"#") and name and str(index.parent / name).casefold() in going:
                continue
            kept_lines.append(line)
        new = b"".join(kept_lines)
        if new != raw:
            group.indexes[index] = new
    group.folders = [root / cs.SAVES / f"Save {slot}", root / cs.LOGS / f"Save {slot}"]
    return group


def _set_aside_groups(folder: Path, slot: int) -> list[Group]:
    """The slot's own "Replaced by copy/move ... - Save <S> - ..." folders in Backups."""
    backups = folder / vv_save_backup.BACKUPS_FOLDER
    out = []
    for name, (kind, _when, _order, label) in sorted(vv_save_backup.backups_index(backups).items()):
        if kind != vv_save_backup.KIND_REPLACED or not re.search(rf" - Save {slot} - ", label):
            continue
        place = next((p for p in backups.iterdir() if p.name.casefold() == name), None) if backups.is_dir() else None
        if place is None or not place.is_dir() or vv_save_backup._is_link(place):
            continue
        group = Group(f"{vv_save_backup.BACKUPS_FOLDER}\\{place.name}", aside=place)
        for path in lp.walk(place, link=vv_save_backup._is_link):
            (group.pictures if is_picture(path) else group.files).append(path)
        out.append(group)
    return out


def _snapshots(folder: Path) -> list[Path]:
    """Every whole-folder copy in Backups (a backup, or a copy that stopped part-way): never a set-aside folder."""
    backups = folder / vv_save_backup.BACKUPS_FOLDER
    if not backups.is_dir():
        return []
    index = vv_save_backup.backups_index(backups)
    out = []
    for entry in sorted(backups.iterdir(), key=lambda p: p.name.casefold()):
        if not entry.is_dir() or vv_save_backup._is_link(entry):
            continue
        found = index.get(entry.name.casefold())
        if found is not None and found[0] != vv_save_backup.KIND_BACKUP:
            continue
        out.append(entry)
    return out


def plan_delete(game: rename.GameSaves, folder: Path, slot: int) -> Plan:
    folder = Path(folder)
    if slot not in cs.SLOTS:
        raise DeleteError("A save slot is 1 to 5.")
    save = game.save_path(folder, slot)
    name = None
    if save.is_file():
        try:
            name = rename.save_name(game, save.read_bytes())
        except OSError as exc:
            raise DeleteError(f"Could not read {save.name}: {exc}") from exc
    index_file = game.index_path(folder)
    before = after = None
    if index_file.is_file():
        before = index_file.read_bytes()
        flag = cs.FLAG_OFFSET[game.number] + slot - 1
        if rename.index_name(game, before, slot) is None or flag >= len(before):
            raise DeleteError(f"The slot list {index_file.name} is not one this tool can read.")
        changed = bytearray(rename._with_name(before, game.index_offset(slot), game.index_stride, rename.EMPTY_SLOT))
        changed[flag] = 0
        after = bytes(changed)
    plan = Plan(game, folder, slot, name, before, after)
    try:
        plan.groups.append(_discover(game, folder, slot, ""))
        for snapshot in _snapshots(folder):
            group = _discover(game, snapshot, slot, f"{vv_save_backup.BACKUPS_FOLDER}\\{snapshot.name}")
            if group.files or group.pictures or group.indexes:
                plan.groups.append(group)
        plan.groups += _set_aside_groups(folder, slot)
    except OSError as exc:
        raise DeleteError(f"Could not list the save folder: {exc}") from exc
    if not plan.files and not plan.pictures:
        raise DeleteError(f"Save {slot} has no files to delete.")
    prints = []
    for path in plan.files + list(plan.pictures):
        try:
            info = lp.stat(path)
            prints.append((str(path).casefold(), info.st_size, info.st_mtime_ns))
        except OSError:
            prints.append((str(path).casefold(), None))
    for group in plan.groups:
        for index in group.indexes:
            info = lp.stat(index)
            prints.append((str(index).casefold(), info.st_size, info.st_mtime_ns))
    import hashlib
    prints.append(("slot list", hashlib.sha256(before).hexdigest() if before is not None else None))
    plan.fingerprints = tuple(sorted(prints, key=lambda f: f[0]))
    return plan


# ---------------------------------------------------------------------------
# The delete
# ---------------------------------------------------------------------------


@dataclass
class DeleteResult:
    folder: Path
    slot: int
    name: str | None
    recycled: list[Path] = field(default_factory=list)
    not_recycled: list[Path] = field(default_factory=list)
    pictures: list[Path] = field(default_factory=list)
    backups_touched: int = 0
    asides: list[Path] = field(default_factory=list)
    problem: str | None = None                   # why it stopped (None: everything went)
    notes: list[str] = field(default_factory=list)


def _refuse_if_running(folder: Path, processes) -> None:
    try:
        cs._refuse_if_running(folder, processes)
    except cs.GameRunning as exc:
        raise GameRunning(str(exc).replace("Copy Player Slot never", "Delete Player Slot never")) from exc


def _write(path: Path, data: bytes) -> None:
    temporary = path.with_name(f"{path.name}.{uuid.uuid4().hex[:12]}.vvfp-delete-tmp")
    with lp.extended(temporary).open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(lp.extended(temporary), lp.extended(path))


def _remove_empty(folders: list[Path]) -> None:
    for root in folders:
        if not lp.is_dir(root) or vv_save_backup._is_link(root):
            continue
        for dirpath, _dirs, _files in sorted(os.walk(lp.extended(root)), key=lambda w: -len(w[0])):
            try:
                os.rmdir(dirpath)                        # only an empty folder: anything left in it stays
            except OSError:
                pass


def _shell(paths: list[Path]) -> None:
    import vv_translations
    vv_translations.recycle(paths)


def delete_slot(game: rename.GameSaves, folder: Path, slot: int, processes=None, now: datetime | None = None,
                expected: tuple | None = None, recycle=None) -> DeleteResult:
    """Send slot ``slot``'s files to the Recycle Bin (see the module's notes).  ``recycle`` replaces the
    Windows call in tests (a list of paths; raises OSError when they cannot all go)."""
    folder = Path(folder)
    controller = processes if processes is not None else vv_save_backup.WindowsProcesses()
    send = recycle or _shell
    when = now or datetime.now()
    _refuse_if_running(folder, controller)
    plan = plan_delete(game, folder, slot)
    if expected is not None and plan.signature() != expected:
        raise DeleteError(f"The files of Save {slot} changed after you confirmed, so nothing was deleted. "
                          "Try again to see the list as it is now.")
    result = DeleteResult(folder, slot, plan.name, pictures=plan.pictures)
    for group in plan.groups:
        try:
            for start in range(0, len(group.files), BATCH):
                batch = group.files[start:start + BATCH]
                send(batch)
                left = [p for p in batch if lp.exists(p)]
                if left:
                    raise OSError(f"{len(left)} file(s) were still there afterwards")
                result.recycled += batch
            for index, data in group.indexes.items():
                _write(index, data)
            if group.aside is not None and not group.pictures:
                _remove_empty([group.aside])
                if not lp.exists(group.aside):
                    vv_save_backup._forget_in_backups_index(group.aside.parent, group.aside.name)
            _remove_empty(group.folders)
            if group.where and group.aside is None:
                result.backups_touched += 1
            if group.aside is not None:
                result.asides.append(group.aside)
        except (OSError, cs.CopyError) as exc:
            result.recycled = [p for p in plan.files if not lp.exists(p)]
            result.not_recycled = [p for p in plan.files if lp.exists(p)]
            result.problem = (f"Windows could not send every file to the Recycle Bin ({exc}), so the delete stopped "
                              f"in {group.where or 'the save folder'}.")
            break
    # The slot list last -- and whenever the slot's save is gone, so it is never listed with no save.
    if plan.index_after is not None and not os.path.lexists(game.save_path(folder, slot)):
        try:
            if game.index_path(folder).read_bytes() == plan.index_before:
                _write(game.index_path(folder), plan.index_after)
        except OSError as exc:
            result.notes.append(f"The slot list could not be updated ({exc}); the game rebuilds it when it starts.")
    backups = folder / vv_save_backup.BACKUPS_FOLDER
    try:
        if backups.is_dir():
            vv_save_backup.note_in_backups_index(
                backups, f"Save {slot} deleted {when:%Y-%m-%d %H%M%S}", KIND_DELETED, when, 1,
                f"Deleted Player Slot: Save {slot} - {plan.name or 'no village'} - {len(result.recycled)} file(s) "
                "sent to the Recycle Bin" + ("" if result.problem is None else f", {len(result.not_recycled)} not"))
    except OSError as exc:
        result.notes.append(f"The Backups index could not be noted ({exc}).")
    return result
