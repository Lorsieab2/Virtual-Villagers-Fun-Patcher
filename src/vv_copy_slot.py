"""Copy Player Slot: copy one save slot's village into an empty slot of the same save folder.

The owner's request: "build the Copy to Player slot in the Virtual Villagers patcher".  The player picks a
slot that has a village and an empty slot, types a name, and the empty slot gets the same village under the
new name -- with every file the patcher keeps for it -- so both can be played from then on.

What one slot is (all five games; docs/rename-tribe.md, measured on the five stock executables and the
owner's saves, read only)
    * The game's own files: the slot save "<stem><S>.ldw" and the two older generations the game rotates
      before every save, "<stem>2<S>.ldw" and "<stem>4<S>.ldw" (never read back by the game).  The slot
      list "<stem>0.ldw" is shared: each slot's name in a fixed-width field and one "in use" byte per slot
      (A New Home and The Lost Children: names at 22, 33 bytes each, the bytes at 187; The Secret City: 22 /
      21 / 127; The Tree of Life and New Believers: 34 / 21 / 139).  At startup every game loads each
      slot's save and rewrites the list from what loads (A New Home 0x41D260, The Secret City 0x4285E0), so
      a slot is in use exactly when its save is there.
    * The tribe's name is in the save buffer (A New Home and The Lost Children +0x8, The Secret City
      +0x12ECC, The Tree of Life +0x170B8, New Believers +0x17D14) and in the slot list.  There is no
      checksum.  The name rule is Rename Tribe's (vv_tribe_rename.name_problem).
    * The patcher's own files of the slot: everything in "Virtual Villagers Fun Patcher\\Save <S>\\" (its
      Logs and Data), the older layout's "Virtual Villagers Fun Patcher Logs\\Save <S>\\" and every
      "... - Save <S>.<ext>" in the patcher's folders, the oldest builds' "<stem>_<S>.dat" beside the saves,
      and the Family Tree Maker's saved trees of the village ("<tribe> (Save <S>) Family Tree.vvtree").

What is copied, and what changes in the copy
    Every one of those files gets a copy for the target slot, "Save <S>" / " - Save <S>" / "(Save <S>)"
    in its path becoming the target's.  The source's files are never changed.  Where a copy's CONTENT
    names the slot or the village, the copy is made to name the target (src/vv_copy_slot.py
    `_transform`): the slot field of every binary file that keeps one (Parentage Records, the logs'
    cross-check and repair-approval markers, the arrival and birth markers, Paid Purchases, Story
    Purchases, the Island Event Timer, The Secret City's Fruit Tree Timers and Second Faction, The Lost
    Children's Elder Totems files, with their own checksums made again); the village ids those markers
    keep (FNV-1a of the "Village: <name> (Save <S>)" line); the logs' "Village: <name> (Save <S>)" lines of
    this village; Log Decisions; and the Like and Dislike Words boundaries of every copied log.  Files the
    game binds by roster or fingerprint (graves, rosters, masks, titles, looks...) are copied byte for byte.
    Every copy keeps its original's file times: several files are believed only while the slot's save
    was written after them.

    NOT copied: the older builds' SHARED logs (no slot in their path; records of every village of the
    game, told apart by their headers), the Backups folder, "Copies Made Before Repairs", any "*.tmp", and
    an older generation of the source that is another village's or already exists for the target.

Safety
    * The game must be closed (it rewrites the slot list when it quits).  Nothing here pauses or closes a
      game.
    * The source must be a readable save of this game; the target must have no save; no file this copy
      would make may exist already (nothing is ever written over).  Only the slot list's target field and
      byte are changed in a file that was there before.
    * Before anything is written the whole save folder is backed up with Back Up Saves' own copier,
      labelled "(before copy)".
    * Every file is written to a temporary file and then moved into place (a new file with a rename that
      fails if the name was taken meanwhile; the slot list with os.replace), and read back.
    * Afterwards the copied save is read with the patcher's own readers (the tribe name, and every villager
      vv_last_names finds, which must be the source's), and it must equal the source byte for byte except
      the name.  Any failure removes every file and folder this copy made and puts the slot list and the
      shared Like and Dislike Words files back as they were.

Nothing here touches Tk; the GUI runs it on a worker thread, and the tests drive it against throwaway save
folders and a fake process list.
"""
from __future__ import annotations

import json
import os
import re
import struct
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import vv_save_backup
import vv_save_layout as layout
import vv_tribe_rename as rename

BACKUP_LABEL = vv_save_backup.BEFORE_COPY
SLOTS = rename.SLOTS
# The slot list's "in use" byte of slot 1, per game (docs/rename-tribe.md; read on the owner's lists).
FLAG_OFFSET = {1: 187, 2: 187, 3: 127, 4: 139, 5: 139}

SAVES = layout.SAVES                       # "Virtual Villagers Fun Patcher"
LOGS = layout.LOGS                         # "Virtual Villagers Fun Patcher Logs"
DATA = layout.DATA                         # "Virtual Villagers Fun Patcher Data"
TREES = layout.TREES                       # "Virtual Villagers Fun Patcher Family Trees"
LEGACY_LOGS = "VVFP Logs"
PATCHER_FOLDERS = tuple(f.casefold() for f in (LOGS, DATA, TREES, LEGACY_LOGS))
_LEGACY_TOP = re.compile(r"^(vv1_masks|vv1_doublers|vv1_parents|vv2_masks|vvfp_masks)_([1-5])\.dat$", re.I)
_TOP_STATISTICS = re.compile(r"^Village Statistics - Save ([1-5])\.txt$", re.I)

# Binary files that keep the slot as a little-endian dword: their first bytes -> where the slot is.
_SLOT_FIELD = {
    b"VP02": 8,     # A New Home's Parentage Records (vv1_parentage.c)
    b"VXC1": 12,    # A New Home's log cross-check marker (vv1_crosscheck.inc)
    b"VRA1": 12,    # Repair Approved (crosscheck_bridge.h)
    b"VCA1": 12,    # Arrivals Recorded (arrival_backfill.h)
    b"VCB1": 12,    # Births Recorded
    b"VPP1": 12,    # Paid Purchases (paid_purchases.h)
    b"VSQ1": 12,    # Story Purchases (story_queue.inc)
    b"VITK": 12,    # Island Event Timer (island_timer_keep.h)
    b"VV3T": 12,    # The Secret City's Fruit Tree Timers (vv3_fruit_timers.h)
    b"VV2F": 12,    # The Secret City's Second Faction (vvfp_vv3_both_factions.c)
}
# Where a marker keeps its village id (FNV-1a of "Village: <name> (Save <S>)"), and its length then.
_VILLAGE_ID = {b"VXC1": (44, 48), b"VCA1": (16, 20), b"VCB1": (16, 20)}
TOTEMS_MAGIC = b"VVFP VV2 TOTEMS\0"
PENDING_MAGIC = b"VVFP VV2 PENDING"


class CopyError(Exception):
    """A copy that was refused or failed, with a reason a player can read."""


class GameRunning(CopyError):
    """The game that uses this save folder is running."""


# ---------------------------------------------------------------------------
# The slots
# ---------------------------------------------------------------------------


@dataclass
class Slots:
    sources: list[rename.SlotInfo]       # slots holding a village this tool can copy
    targets: list[int]                   # empty slots (no save)
    unreadable: list[rename.SlotInfo]    # slots with a save this tool cannot read


def read_slots(game: rename.GameSaves, folder: Path) -> Slots:
    """Which slots can be copied from, and which are empty."""
    sources, targets, unreadable = [], [], []
    for info in rename.read_slots(game, Path(folder)):
        path = game.save_path(Path(folder), info.slot)
        if not os.path.lexists(path):
            targets.append(info.slot)
        elif info.name is not None:
            sources.append(info)
        else:
            unreadable.append(info)
    return Slots(sources, targets, unreadable)


def copy_folders(title: str, documents: Path | None) -> list[Path]:
    """The save folders offered: Rename Tribe's (the patched games' "<title> - Modded..." folders)."""
    return rename.rename_folders(title, documents)


# ---------------------------------------------------------------------------
# Where each file goes
# ---------------------------------------------------------------------------


def _fnv1a32(text: str) -> int:
    h = 2166136261
    for byte in text.encode("latin-1", "replace"):
        h = ((h ^ byte) * 16777619) & 0xFFFFFFFF
    return h or 1


def _rename_slot_in_name(name: str, source: int, target: int) -> str:
    """" - Save <S>" (the last one directly before an extension or the end) and "(Save <S>)" made the
    target's."""
    found = list(re.finditer(rf" - Save {source}(?=\.|$)", name, re.I))
    if found:
        at = found[-1]
        name = name[:at.start()] + f" - Save {target}" + name[at.end():]
    return re.sub(rf"\(Save {source}\)", f"(Save {target})", name, flags=re.I)


def target_relative(relative: Path, source: int, target: int) -> Path | None:
    """Where the target's copy of the patcher file ``relative`` goes, or None when it is not the source
    slot's own (or is never copied)."""
    parts = relative.parts
    if not parts:
        return None
    name = parts[-1]
    if name.casefold().endswith(".tmp") or any(p.casefold() == layout.COPIES.casefold() for p in parts):
        return None
    top = parts[0].casefold()
    if len(parts) == 1:
        match = _LEGACY_TOP.match(name)
        if match and int(match.group(2)) == source:
            return Path(f"{match.group(1)}_{target}.dat")
        match = _TOP_STATISTICS.match(name)
        if match and int(match.group(1)) == source:
            return Path(f"Village Statistics - Save {target}.txt")
        return None
    # Everything of one save in one folder, and the older layout's slot folder of logs: all of it.
    if top in (SAVES.casefold(), LOGS.casefold()) and len(parts) >= 3 \
            and parts[1].casefold() == f"save {source}":
        rest = list(parts[2:])
        rest[-1] = _rename_slot_in_name(rest[-1], source, target)
        return Path(parts[0], f"Save {target}", *rest)
    if top in (SAVES.casefold(), LOGS.casefold()) and re.fullmatch(r"save [1-5]", parts[1].casefold()):
        return None                                 # another slot's folder
    if top not in PATCHER_FOLDERS:
        return None
    if top == TREES.casefold() and len(parts) == 2:
        return None                                 # saved trees: `_plan_trees`
    renamed = _rename_slot_in_name(name, source, target)
    if renamed == name or not re.search(rf" - Save {target}(?=\.|$)", renamed, re.I):
        return None
    return Path(*parts[:-1], renamed)


# ---------------------------------------------------------------------------
# What changes inside a copy
# ---------------------------------------------------------------------------


@dataclass
class LogMap:
    """How a copied log's byte offsets moved when its village lines were rewritten."""
    changes: list[tuple[int, int, int]] = field(default_factory=list)   # (start, old length, new length)

    def offset(self, value: int) -> int:
        moved = value
        for start, old, new in self.changes:
            if value >= start + old:
                moved += new - old
            elif value > start:
                moved += min(value - start, new) - (value - start)
        return moved


def rewrite_log(data: bytes, headers: set[str], new_header: str) -> tuple[bytes, LogMap]:
    """The log with each line that is one of ``headers`` (this village's "Village: <name> (Save <S>)")
    made ``new_header``; every other byte as it was."""
    out = bytearray()
    mapping = LogMap()
    at = 0
    for line in data.splitlines(keepends=True):
        body = line.rstrip(b"\r\n")
        ending = line[len(body):]
        text = body.decode("latin-1")
        if text.rstrip(" \t") in headers:
            replaced = new_header.encode("latin-1", "replace")
            mapping.changes.append((at, len(body), len(replaced)))
            out += replaced + ending
        else:
            out += line
        at += len(line)
    return bytes(out), mapping


def _patch_dword(data: bytearray, at: int, old: int, new: int) -> bool:
    if len(data) >= at + 4 and struct.unpack_from("<I", data, at)[0] == old:
        struct.pack_into("<I", data, at, new)
        return True
    return False


def transform_binary(data: bytes, source: int, target: int, old_ids: set[int], new_id: int,
                     old_name: str, new_name: str) -> bytes:
    """A binary sidecar made the target's: its slot field, its village id, The Lost Children's Elder
    Totems files (slot, village name, checksum).  Anything else, or a file that is not whole, as it was."""
    import vv_vv2_totem_store as totems

    out = bytearray(data)
    head = bytes(out[:4])
    if head in _SLOT_FIELD:
        if not _patch_dword(out, _SLOT_FIELD[head], source, target):
            return data                              # another slot's file kept here: left as it is
        place = _VILLAGE_ID.get(head)
        if place is not None and len(out) == place[1]:
            (current,) = struct.unpack_from("<I", out, place[0])
            if current in old_ids:
                struct.pack_into("<I", out, place[0], new_id)
        return bytes(out)
    if out[:16] in (TOTEMS_MAGIC, PENDING_MAGIC) and len(out) >= 48:
        if struct.unpack_from("<I", out, len(out) - 4)[0] != totems._fnv1a(bytes(out[:-4])):
            return data                              # not whole: the game sets it aside either way
        if not _patch_dword(out, 24, source, target):
            return data
        if out[:16] == TOTEMS_MAGIC and struct.unpack_from("<I", out, 16)[0] == 2 \
                and len(out) >= totems.HEADER + 4:
            cap = totems.VILLAGE_CAP
            field_ = bytes(out[totems.HEADER_V1:totems.HEADER_V1 + cap])
            if field_.split(b"\0", 1)[0].decode("latin-1") == old_name:
                raw = new_name.encode("latin-1", "replace")[:cap - 1]
                out[totems.HEADER_V1:totems.HEADER_V1 + cap] = raw + bytes(cap - len(raw))
        struct.pack_into("<I", out, len(out) - 4, totems._fnv1a(bytes(out[:-4])))
        return bytes(out)
    return data


def transform_decisions(data: bytes, headers: set[str], new_header: str) -> bytes:
    """Log Decisions: each decision of this village filed under the target's village line."""
    try:
        doc = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return data
    if not isinstance(doc, dict) or not isinstance(doc.get("decisions"), list):
        return data
    moved = False
    kept = []
    for d in doc["decisions"]:
        if isinstance(d, dict) and d.get("village") in headers:
            d = {**d, "village": new_header}
            moved = True
        kept.append(d)
    if not moved:
        return data
    return json.dumps({**doc, "decisions": kept}, indent=1).encode("utf-8")


def transform_words(data: bytes, source: int, target: int, maps: dict[str, LogMap]) -> bytes:
    """A save's own Like and Dislike Words file: every boundary of a log in the source's own folder
    made the target's log's (its key, and its offset as the rewritten log has it)."""
    prefix = f"{SAVES}\\Save {source}\\".casefold()
    out = []
    for line in data.decode("utf-8", "replace").splitlines(keepends=True):
        body = line.rstrip("\r\n")
        ending = line[len(body):]
        offset, tab, key = body.partition("\t")
        if tab and key.casefold().startswith(prefix):
            new_key = f"{SAVES}\\Save {target}\\" + key[len(prefix):]
            try:
                value = int(offset)
            except ValueError:
                out.append(line)
                continue
            mapping = maps.get(key.casefold())
            if mapping is not None:
                value = mapping.offset(value)
            out.append(f"{value}\t{new_key}{ending}")
        else:
            out.append(line)
    return "".join(out).encode("utf-8")


# ---------------------------------------------------------------------------
# The plan
# ---------------------------------------------------------------------------


@dataclass
class NewFile:
    path: Path                     # where the copy goes (must not exist)
    data: bytes
    source: Path                   # the file it is a copy of (its times are kept)
    kind: str                      # "save", "generation", "file"


@dataclass
class WordsAppend:
    path: Path                     # a shared Like and Dislike Words file
    line: bytes


@dataclass
class Plan:
    game: rename.GameSaves
    folder: Path
    source: int
    target: int
    old_name: str
    new_name: str
    index_before: bytes
    index_after: bytes
    files: list[NewFile] = field(default_factory=list)
    words: list[WordsAppend] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)        # what was not copied, and why
    source_villagers: list[int] = field(default_factory=list)


def _relative_key(relative: Path) -> str:
    return "\\".join(relative.parts)


def _plan_trees(plan: Plan, headers: set[str], game: rename.GameSaves) -> None:
    """The Family Tree Maker's saved trees of this village (its game, slot and tribe), named for the target."""
    folder = plan.folder / TREES
    try:
        trees = sorted(p for p in folder.glob("*.vvtree") if p.is_file())
    except OSError:
        return
    for path in trees:
        if f"(Save {plan.source})".casefold() not in path.name.casefold():
            continue
        try:
            original = path.read_bytes()
            tree = json.loads(original.decode("utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(tree, dict) or (tree.get("game"), tree.get("slot"), tree.get("tribe")) != (
                game.number, plan.source, plan.old_name):
            continue
        name = _rename_slot_in_name(path.name, plan.source, plan.target)
        if name.startswith(f"{plan.old_name} (Save {plan.target})"):
            name = plan.new_name + name[len(plan.old_name):]
        data = json.dumps({**tree, "slot": plan.target, "tribe": plan.new_name}, indent=1).encode("utf-8")
        plan.files.append(NewFile(folder / name, data, path, "file"))


def plan_copy(game: rename.GameSaves, folder: Path, source: int, target: int, new_name: str) -> Plan:
    """Everything the copy would write, worked out and checked before anything is written."""
    import vv_last_names as ln

    folder = Path(folder)
    if source not in SLOTS or target not in SLOTS:
        raise CopyError("A save slot is 1 to 5.")
    if source == target:
        raise CopyError("Choose two different slots.")
    problem = rename.name_problem(game, new_name)
    if problem is not None:
        raise CopyError(problem)
    save = game.save_path(folder, source)
    try:
        data = save.read_bytes()
    except FileNotFoundError as exc:
        raise CopyError(f"Save {source} has no tribe ({save.name} is missing).") from exc
    except OSError as exc:
        raise CopyError(f"Could not read {save.name}: {exc}") from exc
    old = rename.save_name(game, data)
    save_layout = rename._save_layout(game, data)
    if old is None or save_layout is None:
        raise CopyError(f"{save.name} is not a {game.title} save this tool can read.")
    try:
        villagers = ln._entries(game.number, data)
    except Exception as exc:  # noqa: BLE001 -- any reader failure means the save is not one to copy
        raise CopyError(f"The villagers in {save.name} could not be read ({exc}), so nothing was copied.") from exc
    destination = game.save_path(folder, target)
    if os.path.lexists(destination):
        raise CopyError(f"Save {target} is in use ({destination.name} is there). Choose an empty slot.")
    index_file = game.index_path(folder)
    try:
        index = index_file.read_bytes()
    except OSError as exc:
        raise CopyError(f"Could not read the slot list {index_file.name}: {exc}") from exc
    flag = FLAG_OFFSET[game.number] + target - 1
    if rename.index_name(game, index, target) is None or flag >= len(index):
        raise CopyError(f"The slot list {index_file.name} is not one this tool can read.")
    after = bytearray(rename._with_name(index, game.index_offset(target), game.index_stride, new_name))
    after[flag] = 1
    plan = Plan(game, folder, source, target, old, new_name, index, bytes(after), source_villagers=villagers)
    name_at = save_layout[0] + game.name_offset
    plan.files.append(NewFile(destination, rename._with_name(data, name_at, game.save_field, new_name), save, "save"))
    for generation in rename.GENERATIONS:
        older = game.generation_path(folder, generation, source)
        mine = game.generation_path(folder, generation, target)
        try:
            older_data = older.read_bytes()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise CopyError(f"Could not read {older.name}: {exc}") from exc
        older_layout = rename._save_layout(game, older_data)
        if older_layout is None or rename.save_name(game, older_data) != old:
            plan.skipped.append(f"{older.name}: another village's or not a save, so not copied")
            continue
        if os.path.lexists(mine):
            plan.skipped.append(f"{mine.name}: already there (left as it is; the game never reads it back)")
            continue
        plan.files.append(NewFile(
            mine, rename._with_name(older_data, older_layout[0] + game.name_offset, game.save_field, new_name),
            older, "generation"))

    headers = rename._village_names(game, folder, source, old)
    new_header = rename.village_header(new_name, target)
    old_ids = {_fnv1a32(h) for h in headers}
    new_id = _fnv1a32(new_header)
    try:
        relatives = vv_save_backup.files_to_back_up(folder)
    except OSError as exc:
        raise CopyError(f"Could not list the save folder: {exc}") from exc
    maps: dict[str, LogMap] = {}
    words_own: list[tuple[Path, Path]] = []          # (copy relative, source relative)
    copied: list[tuple[Path, Path]] = []
    for relative in relatives:
        new_relative = target_relative(relative, source, target)
        if new_relative is None:
            continue
        copied.append((relative, new_relative))
    for relative, new_relative in copied:
        path = folder / relative
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise CopyError(f"Could not read {relative}: {exc}") from exc
        name = relative.name
        if layout.is_words_file(path) and relative.parts[0].casefold() == SAVES.casefold():
            words_own.append((relative, new_relative))
            continue
        if name.casefold().endswith(".txt"):
            raw, mapping = rewrite_log(raw, headers, new_header)
            maps[_relative_key(relative).casefold()] = mapping
            # The older layout's logs keep their boundaries in the SHARED words file: a line for the copy.
            if relative.parts[0].casefold() == LOGS.casefold():
                plan.words += _shared_boundary(folder, game.number, relative, new_relative, mapping)
        elif re.search(r" Log Decisions - Save \d\.json$", name, re.I):
            raw = transform_decisions(raw, headers, new_header)
        else:
            raw = transform_binary(raw, source, target, old_ids, new_id, old, new_name)
        plan.files.append(NewFile(folder / new_relative, raw, path, "file"))
    for relative, new_relative in words_own:
        path = folder / relative
        plan.files.append(NewFile(folder / new_relative, transform_words(path.read_bytes(), source, target, maps),
                                  path, "file"))
    _plan_trees(plan, headers, game)
    taken = [f.path for f in plan.files if os.path.lexists(f.path)]
    if taken:
        shown = "; ".join(str(p.relative_to(folder)) for p in taken[:8])
        more = f" and {len(taken) - 8} more" if len(taken) > 8 else ""
        raise CopyError(
            f"Save {target} is empty in the game, but the patcher already keeps files for it: {shown}{more}. "
            "Nothing is ever written over, so nothing was copied. Those files belong to a village that was "
            "in that slot before; move them out of the save folder yourself if you no longer want them.")
    names = [str(f.path).casefold() for f in plan.files]
    if len(names) != len(set(names)):
        raise CopyError("Two of the slot's files would be copied to the same place, so nothing was copied.")
    return plan


def _shared_boundary(folder: Path, game: int, relative: Path, new_relative: Path, mapping: LogMap) -> list[WordsAppend]:
    import vv_log_tools as tools
    import vv_move_to_save_folders as mover

    checker = tools.load_checker()
    try:
        boundary = mover._boundary(folder, game, checker.word_key(_relative_key(relative)))
    except OSError:
        boundary = None
    if boundary is None:
        return []
    key = checker.word_key(_relative_key(new_relative))
    path = layout.words_file_for(folder, game, key)
    return [WordsAppend(path, f"{mapping.offset(boundary)}\t{key}\r\n".encode("utf-8"))]


# ---------------------------------------------------------------------------
# The copy
# ---------------------------------------------------------------------------


@dataclass
class CopyResult:
    folder: Path
    source: int
    target: int
    old_name: str
    new_name: str
    backup: vv_save_backup.BackupResult
    created: list[Path] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    words: list[Path] = field(default_factory=list)


@dataclass
class _Done:
    files: list[Path] = field(default_factory=list)
    dirs: list[Path] = field(default_factory=list)
    words: dict = field(default_factory=dict)     # shared words file -> its size before (None: not there)
    index: bool = False


def _refuse_if_running(folder: Path, processes: vv_save_backup.ProcessController) -> None:
    import vv_log_tools as tools
    try:
        tools._refuse_if_running(folder, processes)
    except tools.GameRunning as exc:
        raise GameRunning(str(exc).replace("Repair Saves & Logs never", "Copy Player Slot never")) from exc
    except tools.LogToolError as exc:
        raise CopyError(str(exc)) from exc


def _make_dirs(path: Path, done: _Done) -> None:
    missing = []
    probe = Path(path)
    while not probe.exists():
        missing.append(probe)
        probe = probe.parent
    for folder in reversed(missing):
        folder.mkdir()
        done.dirs.append(folder)


def _temporary(path: Path) -> Path:
    return path.with_name(f"{path.name}.{uuid.uuid4().hex[:12]}.vvfp-copy-tmp")


def _write_new(path: Path, data: bytes, times: tuple[int, int], done: _Done) -> None:
    """A new file through a temporary one; the move into place fails if the name was taken meanwhile, so
    nothing is ever written over.  Its original's times are kept."""
    _make_dirs(path.parent, done)
    temporary = _temporary(path)
    try:
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.utime(temporary, ns=times)
        os.rename(temporary, path)                     # never replaces on Windows: FileExistsError
    finally:
        if temporary.exists():
            temporary.unlink()
    done.files.append(path)
    if path.read_bytes() != data:
        raise CopyError(f"{path.name} did not read back as written.")
    if abs(os.stat(path).st_mtime_ns - times[1]) > 2_000_000_000:
        raise CopyError(f"The time of {path.name} could not be kept.")


def _replace(path: Path, data: bytes) -> None:
    temporary = _temporary(path)
    try:
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    if path.read_bytes() != data:
        raise CopyError(f"{path.name} did not read back as written.")


def _append_words(item: WordsAppend, done: _Done) -> None:
    with layout.words_lock_for(item.path):
        if item.path not in done.words:
            done.words[item.path] = item.path.stat().st_size if item.path.exists() else None
            _make_dirs(item.path.parent, done)
        with open(item.path, "ab") as handle:
            handle.write(item.line)
            handle.flush()
            os.fsync(handle.fileno())


def _roll_back(plan: Plan, done: _Done) -> list[str]:
    """Remove only what this copy made, and put the slot list and shared words files back."""
    problems: list[str] = []
    if done.index:
        try:
            if plan.game.index_path(plan.folder).read_bytes() != plan.index_before:
                _replace(plan.game.index_path(plan.folder), plan.index_before)
        except (OSError, CopyError) as exc:
            problems.append(f"{plan.game.index_path(plan.folder).name}: {exc}")
    for path, size in done.words.items():
        try:
            with layout.words_lock_for(path):
                if size is None:
                    path.unlink(missing_ok=True)
                else:
                    with path.open("r+b") as handle:
                        handle.truncate(size)
        except OSError as exc:
            problems.append(f"{path.name}: {exc}")
    for path in reversed(done.files):
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            problems.append(f"{path.name}: {exc}")
    for folder in reversed(done.dirs):
        try:
            folder.rmdir()
        except OSError as exc:
            problems.append(f"{folder}: {exc}")
    return problems


def verify(plan: Plan) -> None:
    """The copied save read with the patcher's own readers, and the slot list read back."""
    import vv_last_names as ln

    game = plan.game
    source = game.save_path(plan.folder, plan.source).read_bytes()
    copy = game.save_path(plan.folder, plan.target).read_bytes()
    name = rename.save_name(game, copy)
    if name != plan.new_name or vv_save_backup.read_village_name(game.number, game.save_path(plan.folder, plan.target)) != plan.new_name:
        raise CopyError(f"The copied save does not read back with the name {plan.new_name}.")
    header = rename._save_layout(game, copy)[0]
    start, end = header + game.name_offset, header + game.name_offset + game.save_field
    if len(copy) != len(source) or copy[:start] != source[:start] or copy[end:] != source[end:]:
        raise CopyError("The copied save is not the same village as the source.")
    if ln._entries(game.number, copy) != plan.source_villagers:
        raise CopyError("The copied save's villagers do not read back as the source's.")
    index = game.index_path(plan.folder).read_bytes()
    if rename.index_name(game, index, plan.target) != plan.new_name or index[FLAG_OFFSET[game.number] + plan.target - 1] != 1:
        raise CopyError("The slot list does not read back with the new name.")


def copy_slot(
    game: rename.GameSaves,
    folder: Path,
    source: int,
    target: int,
    new_name: str,
    processes: vv_save_backup.ProcessController | None = None,
    now: datetime | None = None,
    _fail_after: int | None = None,
) -> CopyResult:
    """Copy the village in ``source`` into the empty ``target`` slot of ``folder`` as ``new_name``.

    Refused (CopyError, nothing changed) when the game is running, the name breaks the game's rule, the
    source cannot be read, the target is in use or any file the copy would make exists.  Otherwise the
    folder is backed up first; on any failure everything this copy made is removed again.
    ``_fail_after`` (tests only) makes the copy fail after that many files.
    """
    folder = Path(folder)
    controller = processes if processes is not None else vv_save_backup.WindowsProcesses()
    when = now or datetime.now()
    _refuse_if_running(folder, controller)
    plan = plan_copy(game, folder, source, target, new_name)
    try:
        backup = vv_save_backup.copy_save_folder(folder, when, suffix=BACKUP_LABEL)
    except vv_save_backup.BackupError as exc:
        raise CopyError(f"The backup before copying failed, so nothing was copied. {exc}") from exc
    # The backup took a moment; the game may have been started meanwhile.
    _refuse_if_running(folder, controller)
    done = _Done()
    try:
        for count, item in enumerate(plan.files):
            if _fail_after is not None and count >= _fail_after:
                raise CopyError("stopped for the test")
            info = item.source.stat()
            _write_new(item.path, item.data, (info.st_atime_ns, info.st_mtime_ns), done)
        for item in plan.words:
            _append_words(item, done)
        index_file = game.index_path(folder)
        if index_file.read_bytes() != plan.index_before:
            raise CopyError(f"{index_file.name} changed while the slot was being copied.")
        done.index = True
        _replace(index_file, plan.index_after)
        verify(plan)
    except Exception as exc:  # noqa: BLE001 -- every failure is rolled back
        problems = _roll_back(plan, done)
        if problems:
            raise CopyError(
                f"The copy failed ({exc}) and these could not be put back: {'; '.join(problems)}. "
                f"Your backup is in {backup.backup_folder}.") from exc
        raise CopyError(
            f"The copy failed ({exc}); everything it made was removed and Save {target} is empty again. "
            f"A backup is in {backup.backup_folder}.") from exc
    return CopyResult(folder, source, target, plan.old_name, new_name, backup,
                      [f.path for f in plan.files], plan.skipped, sorted({w.path for w in plan.words}))
