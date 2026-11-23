"""Move Player Slot: move one save slot's village, with EVERYTHING tied to that slot, into another slot of
the same save folder, and leave the slot it came from empty.

The owner (2026-11-22): "add a utility to transfer save files AND BACKUPS AND LOGS AND ALL DATA FILES TIED
TO A SAVE SLOT TO A DIFFERENT SLOT (CAN BE EXTRA DIALOGUES IN COPY PLAYER SLOT)".  It is the "Move" choice
of the Copy Player Slot window (src/vv_copy_slot_window.py).  The village keeps its name, its record
numbers and every file; only the slot changes.

What moves (all five games; the slot's files as Copy Player Slot and Start Over know them,
src/vv_copy_slot.py, native/shared/save_reset.c -- and here nothing of the slot is left behind)
    * The game's own files: the slot save "<stem><S>.ldw" and the two older generations the game rotates
      before every save, "<stem>2<S>.ldw" and "<stem>4<S>.ldw" (every game the same: vv_tribe_rename
      GENERATIONS; New Believers' slot 1 is "...Believers1.ldw", "...Believers21.ldw", "...Believers41.ldw").
      The shared slot list "<stem>0.ldw" gets the village's name and "in use" byte in the target's field and
      the slot-select screen's empty-slot entry ("NEW PLAYER", not in use) in the source's.
    * Everything in "Virtual Villagers Fun Patcher\\Save <S>\\" (the save's Logs and Data: every sidecar,
      its Copies Made Before Repairs, ".before-..." / ".another-village-..." / ".unreadable-..." copies,
      pictures, a companion's ".tmp") and the older layout's "Virtual Villagers Fun Patcher Logs\\Save <S>\\".
    * Every file of the patcher's other folders (Data, Logs, Family Trees, an older build's "VVFP Logs")
      whose name says " - Save <S>" (Copies Made Before Repairs too), the Family Tree Maker's saved trees of
      the slot (by the slot recorded in them), its reports and pictures ("... - Save <S> - Page 2.png"),
      the oldest builds' "<name>_<S>.dat" and "Village Statistics - Save <S>.txt" beside the saves.
    * The village's records in an older build's SHARED logs (no slot in their path; every village's records
      under its "Village: <name> (Save <S>)" line) are carried into the target's own "...Logs\\Save <T>\\"
      logs exactly as Copy Player Slot carries them (the shared logs themselves are never changed).
    The source's whole-folder backups in "Backups" are snapshots of every slot at once and stay as they
    are: restoring one puts the whole folder back as it was then (the village in Save <S>).

What changes in a moved file's name and content
    "Save <S>" / " - Save <S>" / "(Save <S>)" / "_<S>.dat" in its path become the target's, and where its
    CONTENT names the slot it is made to name the target, with Copy Player Slot's own transforms
    (vv_copy_slot): every "Village: <name> (Save <S>)" line of the village (older names keep their name),
    the "Tribe renamed" notes' and the Reconciliation report's slot, Log Decisions, the slot field of every
    binary marker that keeps one (and the village ids they keep), The Lost Children's Elder Totems files,
    the Like and Dislike Words keys, and the slot recorded in a saved family tree.  Nothing is renumbered:
    it is the same village.  Every file keeps its times.

Safety
    * The game must be closed; nothing here pauses or closes one.
    * The whole save folder is backed up first ("Backups\\<date> (before move)").
    * The target's files -- its village when it holds one (the player said Yes to replacing it), or the
      leftovers of an earlier village -- are MOVED, never deleted, into "Backups\\<date> S<T>" ("Replaced by
      move <date> - Save <T> - <village>" in the Backups index), each only once the backup is seen to hold
      it exactly.
    * Files are moved with a rename on the same disk; a file whose content changes is then replaced through
      a temporary file.  Nothing is ever written over: every place a file goes must be free once the
      target's files are set aside.
    * Afterwards the moved save is read with the patcher's own readers and every moved file is read back.
      Any failure moves every file back, puts every changed byte back and returns the set-aside files.
    * A "Repair <n>" record in the target's Repairs Made log lists every file moved.

Nothing here touches Tk; the GUI runs it on a worker thread, and the tests drive it against throwaway save
folders and a fake process list.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import vv_copy_slot as cs
import vv_long_paths as lp
import vv_save_backup
import vv_save_layout as layout
import vv_tribe_rename as rename

BACKUP_LABEL = vv_save_backup.BEFORE_MOVE
SET_ASIDE_PREFIX = "Replaced by move "
SLOTS = cs.SLOTS
TITLE = "Move Player Slot"

SAVES, LOGS, DATA, TREES, LEGACY_LOGS = cs.SAVES, cs.LOGS, cs.DATA, cs.TREES, cs.LEGACY_LOGS
_SLOT_FOLDER = re.compile(r"(?i)save [1-5]")
_PICTURES = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".html", ".htm")
_KEPT_MARKS = (".before-", ".another-village-", ".unreadable-")


class MoveError(cs.CopyError):
    """A move that was refused or failed, with a reason a player can read."""


class GameRunning(MoveError):
    """The game that uses this save folder is running."""


# ---------------------------------------------------------------------------
# Every file of one slot
# ---------------------------------------------------------------------------


def _files(root: Path, skip=None) -> list[Path]:
    if not lp.is_dir(root) or vv_save_backup._is_link(root):
        return []
    return list(lp.walk(root, skip=skip, link=vv_save_backup._is_link))


def slot_everything(game: rename.GameSaves, folder: Path, slot: int) -> list[Path]:
    """Every file tied to slot ``slot`` (see the module's notes), sorted: what a move takes from a source,
    and what it sets aside in a target.  Never anything in Backups."""
    folder = Path(folder)
    out: list[Path] = []
    for path in [game.save_path(folder, slot)] + [game.generation_path(folder, g, slot) for g in rename.GENERATIONS]:
        if lp.is_file(path):
            out.append(path)
    for top in (SAVES, LOGS):
        out += _files(folder / top / f"Save {slot}")
    tops = {SAVES.casefold(), LOGS.casefold()}

    def other_places(d: Path) -> bool:
        """The slot folders (above) and the older reports folder (below) are not walked by name."""
        parent = d.parent
        return (parent.parent == folder and parent.name.casefold() in tops and bool(_SLOT_FOLDER.fullmatch(d.name))) \
            or (parent == folder / LOGS and d.name.casefold() == "genealogy")

    for top in (SAVES, DATA, LOGS, LEGACY_LOGS):
        for path in _files(folder / top, skip=other_places):
            if cs._name_game(path.name) not in (0, game.number):
                continue
            if cs._name_slot(path.name, trees=False) == slot:
                out.append(path)
    for root in (folder / TREES, folder / LOGS / "Genealogy"):
        for path in _files(root):
            name = path.name
            if cs._name_game(name) not in (0, game.number):
                continue
            said = cs._name_slot(name, trees=True)
            if ".vvtree" in name.casefold():
                record = cs._tree_record(path) if name.casefold().endswith(".vvtree") else None
                if record is None:
                    if said == slot:
                        out.append(path)          # named for the slot, its content not readable: by its name
                    continue
                if record[0] not in (0, game.number) or (said and said != record[1]):
                    continue                      # its save cannot be told: left where it is
                if record[1] == slot:
                    out.append(path)
            elif said == slot:
                out.append(path)
    try:
        entries = sorted(folder.iterdir(), key=lambda p: p.name.casefold())
    except OSError:
        entries = []
    for entry in entries:
        if not entry.is_file():
            continue
        legacy = cs._LEGACY_TOP.match(entry.name)
        top = cs._TOP_STATISTICS.match(entry.name)
        if (legacy and int(legacy.group(2)) == slot) or (top and int(top.group(1)) == slot):
            out.append(entry)
    unique: dict[str, Path] = {}
    for path in out:
        unique.setdefault(str(path).casefold(), path)
    return sorted(unique.values(), key=lambda p: str(p).casefold())


# ---------------------------------------------------------------------------
# Where each file goes
# ---------------------------------------------------------------------------


def moved_name(name: str, source: int, target: int) -> str:
    """A file name made the target's: its LAST " - Save <S>" directly before an extension, a space (the
    Family Tree reports' "... - Save <S> - Page 2.png") or the end, and its last "(Save <S>)"."""
    found = list(re.finditer(rf" - Save {source}(?=[. ]|$)", name, re.I))
    if found:
        at = found[-1]
        name = name[:at.start()] + f" - Save {target}" + name[at.end():]
    found = list(re.finditer(rf"\(Save {source}\)", name, re.I))
    if found:
        at = found[-1]
        name = name[:at.start()] + f"(Save {target})" + name[at.end():]
    return name


def moved_relative(game: rename.GameSaves, relative: Path, source: int, target: int) -> Path:
    """Where the slot's file ``relative`` (inside the save folder) goes in the target slot."""
    parts = relative.parts
    if len(parts) == 1:
        name = parts[0]
        here = Path()
        pairs = [(game.save_path(here, source).name, game.save_path(here, target).name)]
        pairs += [(game.generation_path(here, g, source).name, game.generation_path(here, g, target).name)
                  for g in rename.GENERATIONS]
        for old, new in pairs:
            if name.casefold() == old.casefold():
                return Path(new)
        legacy = cs._LEGACY_TOP.match(name)
        if legacy:
            return Path(f"{legacy.group(1)}_{target}.dat")
        if cs._TOP_STATISTICS.match(name):
            return Path(f"Village Statistics - Save {target}.txt")
        return Path(moved_name(name, source, target))
    if parts[0].casefold() in (SAVES.casefold(), LOGS.casefold()) and parts[1].casefold() == f"save {source}":
        rest = list(parts[2:])
        rest[-1] = moved_name(rest[-1], source, target)
        return Path(parts[0], f"Save {target}", *rest)
    return Path(*parts[:-1], moved_name(parts[-1], source, target))


def _kept_copy(name: str) -> bool:
    """A copy kept beside or before a file (".before-...", a set-aside or unreadable one, a ".tmp")."""
    low = name.casefold()
    return any(mark in low for mark in _KEPT_MARKS) or low.endswith(".tmp") or ".vvfp-" in low


def _base_name(name: str) -> str:
    """The name of the file a kept copy is of (``X - Save 1.dat.before-repair`` -> ``X - Save 1.dat``)."""
    low = name.casefold()
    cut = len(name)
    for mark in _KEPT_MARKS:
        at = low.find(mark)
        if at >= 0:
            cut = min(cut, at)
    base = name[:cut]
    return base[:-4] if base.casefold().endswith(".tmp") else base


# ---------------------------------------------------------------------------
# The plan
# ---------------------------------------------------------------------------


@dataclass
class Move:
    source: Path                   # the file now
    target: Path                   # where it goes (the same place for a file whose name has no slot)
    original: bytes                # its bytes now
    data: bytes | None = None      # its new bytes, None: as they are


@dataclass
class Plan:
    game: rename.GameSaves
    folder: Path
    source: int
    target: int
    name: str
    index_before: bytes
    index_after: bytes
    moves: list[Move] = field(default_factory=list)
    files: list[cs.NewFile] = field(default_factory=list)       # the shared logs' records, for the target
    words: list[cs.WordsAppend] = field(default_factory=list)
    removals: list[Path] = field(default_factory=list)          # the target's files, set aside
    overwritten: str | None = None                              # the village replaced ("" unreadable)
    source_villagers: list = field(default_factory=list)

    def signature(self) -> tuple:
        """What the player was shown: every move and every file set aside."""
        return (tuple(sorted((str(m.source).casefold(), str(m.target).casefold()) for m in self.moves)),
                tuple(sorted(str(f.path).casefold() for f in self.files)),
                tuple(sorted(str(p).casefold() for p in self.removals)))

    def preview(self) -> list[str]:
        """Every change, one line each: "<from>  ->  <to>" (a file whose name keeps no slot: "(updated)")."""
        rel = lambda p: str(Path(p).relative_to(self.folder))            # noqa: E731
        lines = []
        for m in self.moves:
            changed = " (slot updated inside)" if m.data is not None else ""
            if str(m.source).casefold() == str(m.target).casefold():
                lines.append(f"{rel(m.source)}{changed or ' (unchanged)'}")
            else:
                lines.append(f"{rel(m.source)}  ->  {rel(m.target)}{changed}")
        for f in self.files:
            lines.append(f"(the village's records in the older shared logs)  ->  {rel(f.path)}")
        return lines


def _refuse_if_running(folder: Path, processes) -> None:
    try:
        cs._refuse_if_running(folder, processes)
    except cs.GameRunning as exc:
        raise GameRunning(str(exc).replace("Copy Player Slot never", "Move Player Slot never")) from exc


def taken_message(name: str, slot: int) -> str:
    return (f"{name} was also the name of an earlier village in Save {slot}, and its old records still use "
            f"it, so this village can't move into Save {slot}. Choose another slot.")


def _new_tree(raw: bytes, game: int, source: int, target: int) -> bytes | None:
    try:
        tree = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    if not isinstance(tree, dict) or tree.get("slot") != source or tree.get("game") not in (None, game):
        return None
    return json.dumps({**tree, "slot": target}, indent=1).encode("utf-8")


def plan_move(game: rename.GameSaves, folder: Path, source: int, target: int) -> Plan:
    """Everything the move would do, worked out and checked before anything is written."""
    import vv_last_names as ln
    import vv_log_tools as tools
    from vv_genealogy_window import tree_file_name

    folder = Path(folder)
    if source not in SLOTS or target not in SLOTS:
        raise MoveError("A save slot is 1 to 5.")
    if source == target:
        raise MoveError("Choose two different slots.")
    save = game.save_path(folder, source)
    try:
        data = save.read_bytes()
    except FileNotFoundError as exc:
        raise MoveError(f"Save {source} has no tribe ({save.name} is missing).") from exc
    except OSError as exc:
        raise MoveError(f"Could not read {save.name}: {exc}") from exc
    name = rename.save_name(game, data)
    if name is None or rename._save_layout(game, data) is None:
        raise MoveError(f"{save.name} is not a {game.title} save this tool can read.")
    try:
        villagers = ln._entries(game.number, data)
    except Exception as exc:  # noqa: BLE001 -- any reader failure means the save is not one to move
        raise MoveError(f"The villagers in {save.name} could not be read ({exc}), so nothing was moved.") from exc
    destination = game.save_path(folder, target)
    if os.path.lexists(destination) and not destination.is_file():
        raise MoveError(f"{destination.name} is not a file, so nothing can be moved into Save {target}.")
    overwritten = None
    if destination.is_file():
        try:
            overwritten = rename.save_name(game, destination.read_bytes()) or ""
        except OSError as exc:
            raise MoveError(f"Could not read {destination.name}: {exc}") from exc
    index_file = game.index_path(folder)
    try:
        index = index_file.read_bytes()
    except OSError as exc:
        raise MoveError(f"Could not read the slot list {index_file.name}: {exc}") from exc
    flag_to = cs.FLAG_OFFSET[game.number] + target - 1
    flag_from = cs.FLAG_OFFSET[game.number] + source - 1
    if rename.index_name(game, index, target) is None or max(flag_to, flag_from) >= len(index):
        raise MoveError(f"The slot list {index_file.name} is not one this tool can read.")
    after = bytearray(rename._with_name(index, game.index_offset(target), game.index_stride, name))
    after = bytearray(rename._with_name(bytes(after), game.index_offset(source), game.index_stride, rename.EMPTY_SLOT))
    after[flag_to], after[flag_from] = 1, 0
    # The older shared logs are never changed: a name an earlier village of the target slot keeps records
    # under there would make every reader take those records for this village's own history.
    headers = rename._village_names(game, folder, source, name)
    taken = cs.shared_log_names(folder, target)
    for header in sorted(headers):
        match = cs._HEADER.match(header)
        if match and match.group(1) in taken:
            raise MoveError(taken_message(match.group(1), target))

    plan = Plan(game, folder, source, target, name, index, bytes(after), overwritten=overwritten,
                source_villagers=villagers)
    try:
        everything = slot_everything(game, folder, source)
        plan.removals = slot_everything(game, folder, target)
    except OSError as exc:
        raise MoveError(f"Could not list the save folder: {exc}") from exc

    new_header = rename.village_header(name, target)
    mapped = cs.header_map(headers, rename.village_header(name, source), new_header, source, target)
    ids = {cs._fnv1a32(h): cs._fnv1a32(mapped[h]) for h in headers}
    note = (name, name, source, target)
    recon = {f"Save {source}: {name}": f"Save {target}: {name}"}
    canonical = tree_file_name(name, source).casefold()

    moves: dict[str, Move] = {}
    texts: dict[str, tuple[Path, list[tuple[int, cs.Piece]]]] = {}
    words_own: list[Move] = []

    def add_text(destination: Path, rank: int, piece: cs.Piece) -> None:
        key = cs._relative_key(destination).casefold()
        texts.setdefault(key, (destination, []))[1].append((rank, piece))

    for path in everything:
        relative = path.relative_to(folder)
        new_relative = moved_relative(game, relative, source, target)
        if relative.parts[0].casefold() == TREES.casefold() and path.name.casefold() == canonical:
            new_relative = Path(*relative.parts[:-1], tree_file_name(name, target))
        try:
            raw = lp.read_bytes(path)
        except OSError as exc:
            raise MoveError(f"Could not read {relative}: {exc}") from exc
        move = Move(path, folder / new_relative, raw)
        moves[str(path).casefold()] = move
        base = _base_name(path.name)
        low = base.casefold()
        if len(relative.parts) == 1 and low.endswith(".ldw"):
            continue                                             # the save and its generations: as they are
        if path.name.casefold().endswith(".tmp") or low.endswith(_PICTURES):
            continue                                             # half-written, or a picture: as it is
        if layout.is_words_file(Path(base)) and relative.parts[0].casefold() == SAVES.casefold():
            words_own.append(move)
        elif low.endswith(".txt"):
            if _kept_copy(path.name):
                move.data, _map = cs.rewrite_log(raw, mapped, new_header, None, recon, note)
            else:
                add_text(new_relative, 2, cs.Piece(relative, raw, [(0, len(raw))]))
        elif re.search(r" Log Decisions - Save \d\.json$", base, re.I):
            move.data = cs.transform_decisions(raw, mapped, new_header, None)
        elif low.endswith(".vvtree"):
            move.data = _new_tree(raw, game.number, source, target)
        elif low.endswith(".json"):
            pass
        else:
            move.data = cs.transform_binary(raw, source, target, ids, name, name)
    cs._plan_shared_logs(folder, source, target, headers, [p.relative_to(folder) for p in everything], add_text)

    checker = tools.load_checker()
    maps: dict[str, cs.LogMap] = {}
    for key, (dest, pieces) in texts.items():
        pieces.sort(key=lambda item: item[0])
        normalised = False
        if len(pieces) > 1:
            cs._drop_older_duplicates(pieces)
            if game.number in checker.WORD_FIXES:
                cs._normalise_words(folder, game.number, checker, pieces)
                normalised = True
        assembled = b"".join(piece.text() for _rank, piece in pieces)
        text, mapping = cs.rewrite_log(assembled, mapped, new_header, None, recon, note)
        own = next((piece for rank, piece in pieces if rank == 2), None)
        if own is not None:
            moves[str(folder / own.relative).casefold()].data = text
        else:
            plan.files.append(cs.NewFile(folder / dest, text, folder / pieces[0][1].relative, "file"))
        if dest.parts[0].casefold() == SAVES.casefold():
            if own is not None:
                maps[cs._relative_key(own.relative).casefold()] = mapping
        elif normalised:
            words_key = checker.word_key(cs._relative_key(dest))
            plan.words.append(cs.WordsAppend(layout.words_file_for(folder, game.number, words_key),
                                             f"0\t{words_key}\r\n".encode("utf-8")))
        else:
            plan.words += cs._shared_boundary(folder, game.number, checker, dest, pieces, mapping)
    for move in words_own:
        move.data = cs.transform_words(move.original, source, target, maps)
    for move in moves.values():
        if move.data is not None and move.data == move.original:
            move.data = None
    plan.moves = sorted(moves.values(), key=lambda m: str(m.source).casefold())
    plan.words += _source_boundaries(folder, game.number, checker, plan)
    # The target's old-layout logs set aside: a boundary of their own (Copy Player Slot's rule).
    shape = SimpleNamespace(folder=folder, words=plan.words, removals=plan.removals,
                            files=[SimpleNamespace(path=m.target, data=m.data if m.data is not None else m.original)
                                   for m in plan.moves] + plan.files)
    plan.words += cs._stale_boundaries(folder, game.number, checker, shape)

    # Every place a file goes must be free once the target's files are set aside (or be the file itself).
    removing = {str(p).casefold() for p in plan.removals}
    sources = {str(m.source).casefold() for m in plan.moves}
    places = [m.target for m in plan.moves] + [f.path for f in plan.files]
    taken_places = [p for p in places if os.path.lexists(p) and str(p).casefold() not in removing
                    and str(p).casefold() not in sources]
    taken_places += [p for p in cs._older_counterparts(folder, places)
                     if str(p).casefold() not in removing and str(p).casefold() not in sources]
    if taken_places:
        shown = "; ".join(str(p.relative_to(folder)) for p in taken_places[:8])
        more = f" and {len(taken_places) - 8} more" if len(taken_places) > 8 else ""
        raise MoveError(f"These files the move would make are already there and are not Save {target}'s alone: "
                        f"{shown}{more}. Nothing is ever written over, so nothing was moved.")
    names = [str(p).casefold() for p in places]
    if len(names) != len(set(names)):
        raise MoveError("Two of the slot's files would go to the same place, so nothing was moved.")
    return plan


def _source_boundaries(folder: Path, game: int, checker, plan: Plan) -> list[cs.WordsAppend]:
    """The source's old-layout logs leave: a Like and Dislike Words line that names one of them is
    followed by "0" (nothing old), so it can never apply to a later log of that name (log_words.h: the last
    line naming a file counts).  The target's lines are written above."""
    import vv_move_to_save_folders as mover

    written = {w.line.decode("utf-8").split("\t", 1)[1].strip().casefold() for w in plan.words}
    out: list[cs.WordsAppend] = []
    for move in plan.moves:
        rel = move.source.relative_to(folder)
        if rel.parts[0].casefold() != LOGS.casefold() or not move.source.name.casefold().endswith(".txt"):
            continue
        key = checker.word_key(cs._relative_key(rel))
        if key.casefold() in written:
            continue
        try:
            stale = mover._boundary(folder, game, key)
        except OSError:
            stale = None
        if stale is None:
            continue
        out.append(cs.WordsAppend(layout.words_file_for(folder, game, key), f"0\t{key}\r\n".encode("utf-8")))
        written.add(key.casefold())
    return out


# ---------------------------------------------------------------------------
# The move
# ---------------------------------------------------------------------------


@dataclass
class MoveResult:
    folder: Path
    source: int
    target: int
    name: str
    backup: vv_save_backup.BackupResult
    moved: list[tuple[Path, Path]] = field(default_factory=list)
    updated: list[Path] = field(default_factory=list)            # moved files whose content names the target now
    created: list[Path] = field(default_factory=list)
    removed: list[Path] = field(default_factory=list)            # the target's files, set aside
    set_aside: Path | None = None
    overwritten: str | None = None
    notes: list[str] = field(default_factory=list)


@dataclass
class _Done(cs._Done):
    moved: list = field(default_factory=list)          # (Move, rewritten?)
    removed_dirs: list = field(default_factory=list)   # the source's folders left empty, removed
    index_times: tuple | None = None                   # the slot list's times before (put back with it)
    words_times: dict = field(default_factory=dict)    # each shared words file's times before


def _temporary(path: Path) -> Path:
    return path.with_name(f"{path.name}.{uuid.uuid4().hex[:12]}.vvfp-move-tmp")


def _write_over(path: Path, data: bytes, times: tuple[int, int]) -> None:
    """``path``'s content replaced through a temporary file, its times kept, read back."""
    temporary = _temporary(path)
    try:
        with lp.extended(temporary).open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.utime(lp.extended(temporary), ns=times)
        os.replace(lp.extended(temporary), lp.extended(path))
    finally:
        if lp.exists(temporary):
            lp.unlink(temporary)
    if lp.read_bytes(path) != data:
        raise MoveError(f"{path.name} did not read back as written.")


def _move_one(move: Move, done: _Done, fail: bool = False) -> None:
    info = lp.stat(move.source)
    times = (info.st_atime_ns, info.st_mtime_ns)
    same_place = str(move.source).casefold() == str(move.target).casefold()
    if not same_place:
        cs._make_dirs(move.target.parent, done)
        os.rename(lp.extended(move.source), lp.extended(move.target))     # never over anything: FileExistsError
    done.moved.append([move, False])
    if fail:
        raise MoveError("stopped for the test")
    if move.data is not None:
        done.moved[-1][1] = True
        _write_over(move.target, move.data, times)
    if lp.read_bytes(move.target) != (move.data if move.data is not None else move.original):
        raise MoveError(f"{move.target.name} did not read back after the move.")


def _remove_empty_folders(plan: Plan, done: _Done) -> None:
    """The source's own folders, emptied by the move, removed (deepest first)."""
    for top in (SAVES, LOGS):
        root = plan.folder / top / f"Save {plan.source}"
        if not lp.is_dir(root) or vv_save_backup._is_link(root):
            continue
        folders = [Path(dirpath) for dirpath, _dirs, _files in os.walk(root)]
        for sub in sorted(folders, key=lambda p: -len(p.parts)):
            try:
                if not any(sub.iterdir()):
                    sub.rmdir()
                    done.removed_dirs.append(sub)
            except OSError:
                pass


def _roll_back(plan: Plan, done: _Done) -> list[str]:
    problems: list[str] = []
    for folder in reversed(done.removed_dirs):
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            problems.append(f"{folder}: {exc}")
    if done.index:
        try:
            if plan.game.index_path(plan.folder).read_bytes() != plan.index_before:
                cs._replace(plan.game.index_path(plan.folder), plan.index_before)
            if done.index_times is not None:
                os.utime(plan.game.index_path(plan.folder), ns=done.index_times)
        except (OSError, cs.CopyError) as exc:
            problems.append(f"{plan.game.index_path(plan.folder).name}: {exc}")
    for path, size in done.words.items():
        try:
            with layout.words_lock_for(path):
                if size is None:
                    path.unlink(missing_ok=True)
                else:
                    with path.open("r+b") as handle:
                        handle.truncate(size)
                    if path in done.words_times:
                        os.utime(path, ns=done.words_times[path])
        except OSError as exc:
            problems.append(f"{path.name}: {exc}")
    for path in reversed(done.files):
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            problems.append(f"{path.name}: {exc}")
    for move, rewritten in reversed(done.moved):
        try:
            if rewritten:
                info = lp.stat(move.target)
                _write_over(move.target, move.original, (info.st_atime_ns, info.st_mtime_ns))
            if str(move.source).casefold() != str(move.target).casefold():
                cs._make_dirs(move.source.parent, cs._Done())
                os.rename(lp.extended(move.target), lp.extended(move.source))
        except (OSError, cs.CopyError) as exc:
            problems.append(f"{move.source.name} (now {move.target}): {exc}")
    for path, moved in reversed(done.removed):
        try:
            cs._put_back(path, moved)
        except (OSError, cs.CopyError) as exc:
            problems.append(f"{path.name} (set aside as {moved}): {exc}")
    for folder in reversed(done.dirs):
        try:
            folder.rmdir()
        except OSError as exc:
            problems.append(f"{folder}: {exc}")
    return problems


def verify(plan: Plan) -> None:
    """The moved save read with the patcher's own readers, the source left empty, every file read back, and
    the slot list read back."""
    import vv_last_names as ln

    game = plan.game
    if os.path.lexists(game.save_path(plan.folder, plan.source)):
        raise MoveError(f"Save {plan.source} still has a save after the move.")
    moved = game.save_path(plan.folder, plan.target)
    data = moved.read_bytes()
    original = next(m.original for m in plan.moves if m.target == moved)
    if data != original:
        raise MoveError("The moved save is not the village that was moved.")
    if rename.save_name(game, data) != plan.name or vv_save_backup.read_village_name(game.number, moved) != plan.name:
        raise MoveError(f"The moved save does not read back with the name {plan.name}.")
    if ln._entries(game.number, data) != plan.source_villagers:
        raise MoveError("The moved save's villagers do not read back as they were.")
    for m in plan.moves:
        if str(m.source).casefold() != str(m.target).casefold() and lp.exists(m.source):
            raise MoveError(f"{m.source.name} is still in Save {plan.source}.")
        if lp.read_bytes(m.target) != (m.data if m.data is not None else m.original):
            raise MoveError(f"{m.target.name} did not read back after the move.")
    index = game.index_path(plan.folder).read_bytes()
    if index != plan.index_after:
        raise MoveError("The slot list does not read back as written.")


def note_move(plan: Plan, result: MoveResult, now: datetime) -> None:
    """One "Repair <n>" record in the target's Repairs Made log: every file moved (old -> new), the
    files set aside, the backup."""
    import vv_log_tools as tools

    folder = plan.folder
    header = rename.village_header(plan.name, plan.target)
    path, text = tools.repair_record_start(folder, plan.game.number, header, plan.target, now)
    text += f"  Checked: every file of Save {plan.source} ({TITLE}: the village moved to Save {plan.target})\r\n"
    for source, target in result.moved:
        text += f"  Moved: {source.relative_to(folder)} -> {target.relative_to(folder)}\r\n"
    for made in result.created:
        text += f"  Added: {made.relative_to(folder)} (the village's records in the older shared logs)\r\n"
    if result.set_aside is not None:
        text += (f"  Set aside: {len(result.removed)} file(s) Save {plan.target} held before, in "
                 f"{result.set_aside.relative_to(folder)}\r\n")
    text += f"  Backup: {result.backup.backup_folder.relative_to(folder)}\r\n\r\n"
    with open(path, "ab") as log:
        log.write(text.encode(cs.GAME_TEXT, "replace"))


def move_slot(
    game: rename.GameSaves,
    folder: Path,
    source: int,
    target: int,
    processes: vv_save_backup.ProcessController | None = None,
    now: datetime | None = None,
    expected: tuple | None = None,
    _fail_after: int | None = None,
) -> MoveResult:
    """Move the village in ``source`` and everything tied to that slot into ``target``.

    Refused (MoveError, nothing changed) when the game is running, the source cannot be read, or a place a
    file would go is taken by something that is not the target's.  Otherwise the folder is backed up first,
    the target's files are set aside once the backup is seen to hold each one, and every file is moved; on
    any failure everything is put back.  ``expected`` is the plan the player was shown (Plan.signature): a
    different plan now refuses the move.  ``_fail_after`` (tests only) makes the move fail after that many
    files."""
    folder = Path(folder)
    controller = processes if processes is not None else vv_save_backup.WindowsProcesses()
    when = now or datetime.now()
    _refuse_if_running(folder, controller)
    plan = plan_move(game, folder, source, target)
    if expected is not None and plan.signature() != expected:
        raise MoveError(f"The files of Save {source} or Save {target} changed after you confirmed, so nothing "
                        "was moved. Try again to see the list as it is now.")
    try:
        backup = vv_save_backup.copy_save_folder(folder, when, suffix=BACKUP_LABEL)
    except vv_save_backup.BackupError as exc:
        raise MoveError(f"The backup before moving failed, so nothing was moved. {exc}") from exc
    _refuse_if_running(folder, controller)        # the backup took a moment
    done = _Done()
    aside = None
    try:
        if plan.removals:
            aside = cs.set_aside_folder(folder, when, target, plan.overwritten, prefix=SET_ASIDE_PREFIX)
            cs._set_aside(plan, backup, aside, done)
        for count, move in enumerate(plan.moves):
            _move_one(move, done, fail=_fail_after is not None and count >= _fail_after)
        for item in plan.files:
            info = item.source.stat()
            cs._write_new(item.path, item.data, (info.st_atime_ns, info.st_mtime_ns), done)
        for item in plan.words:
            if item.path not in done.words_times and item.path.exists():
                info = item.path.stat()
                done.words_times[item.path] = (info.st_atime_ns, info.st_mtime_ns)
            cs._append_words(item, done)
        index_file = game.index_path(folder)
        if index_file.read_bytes() != plan.index_before:
            raise MoveError(f"{index_file.name} changed while the slot was being moved.")
        info = index_file.stat()
        done.index_times = (info.st_atime_ns, info.st_mtime_ns)
        done.index = True
        cs._replace(index_file, plan.index_after)
        _remove_empty_folders(plan, done)
        verify(plan)
    except Exception as exc:  # noqa: BLE001 -- every failure is rolled back
        problems = _roll_back(plan, done)
        if aside is not None:
            cs._drop_empty_aside(aside)
        if problems:
            raise MoveError(
                f"The move failed ({exc}) and these could not be put back: {'; '.join(problems)}. "
                f"Your backup is in {backup.backup_folder}.") from exc
        raise MoveError(
            f"The move failed ({exc}); every file was put back and Save {source} and Save {target} are as they "
            f"were. A backup is in {backup.backup_folder}.") from exc
    result = MoveResult(folder, source, target, plan.name, backup,
                        [(m.source, m.target) for m in plan.moves], [m.target for m in plan.moves if m.data is not None],
                        [f.path for f in plan.files], list(plan.removals), aside, plan.overwritten)
    try:
        note_move(plan, result, when)
    except Exception as exc:  # noqa: BLE001 -- the record is only the Repairs log's; the move stands
        result.notes.append(f"Save {target}'s Repairs Made log could not be written ({exc}).")
    return result
