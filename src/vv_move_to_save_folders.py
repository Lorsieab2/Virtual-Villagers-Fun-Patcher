"""Repair Saves & Logs' "Move Files to Save Folders..." (the owner, 2026-10-17: "ADD A BUTTON TO MOVE
EXISTING FILES TO ITS SAVE FOLDER").

Everything the patcher keeps about save slot S now goes in one folder (src/vv_save_layout.py, "One
folder per save slot ..."):

    <save folder>\\Virtual Villagers Fun Patcher\\Save <S>\\Logs\\...
    <save folder>\\Virtual Villagers Fun Patcher\\Save <S>\\Data\\...

An older save's files stay in "Virtual Villagers Fun Patcher Logs\\Save <S>\\" and "Virtual Villagers
Fun Patcher Data\\<kind>\\<name> - Save <S>.<ext>", where every reader still finds them
(vv_save_layout.route).  NOTHING MOVES THEM ON ITS OWN: only this button, pressed by the player, for
one save folder (one game, every save slot 1-5), with the game closed, and only when the game's
installed patch reads the save folders (every patch DLL that knows the older folders also knows
"Virtual Villagers Fun Patcher\\Save "):

  1. what moves, from where to where, and what is not moved and why, is listed (`plan`) and the player
     is asked first (Cancel is the default);
  2. every file is copied to "Copies Made Before Repairs" (vv_log_tools.copy_before_repair, " (before
     move to save folder)", "-2", "-3"... when taken) and the copy read back;
  3. every file is copied to its new place (never replacing anything: "xb"), its times copied, and read
     back;
  4. each moved log's Like and Dislike Words boundary (the smallest any words file records) is copied,
     under its new name, into the save's own words file (the shared file is never split or changed);
  5. with the game still closed, each original is removed once its new copy still matches the copy
     made first;
  6. the older log folders the move left truly empty are removed (os.rmdir; nothing else);
  7. one record per save slot moved is written in that save's Repairs Made log.

When anything in 2-6 fails, everything is put back: every removed original restored from its copy (and
read back), every new copy this run made removed, every words file cut back to what it was; the copies
made first are kept.  Backups, the shared older logs, the shared Like and Dislike Words, the Family
Trees and the game's own saves are never touched."""
from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import vv_log_tools as tools
import vv_save_backup
import vv_save_layout as layout

TITLE = "Move Files to Save Folders"
COPY_SUFFIX = " (before move to save folder)"
PATCH_FILES = "Virtual Villagers Fun Patcher Files"
# What a patch DLL that writes the older layout carries, and what one that reads the save folders
# carries (native/shared/per_save.h): the literal text `Virtual Villagers Fun Patcher\Save `.
OLD_LAYOUT_NAMES = (layout.LOGS, layout.DATA)
NEW_LAYOUT_MARKER = f"{layout.SAVES}\\Save "
GAME_TITLES = {1: "A New Home", 2: "The Lost Children", 3: "The Secret City", 4: "The Tree of Life",
               5: "New Believers"}

# Why a file or folder is not moved.
R_OLD_NAME = ("still under an older build's name: choose \"Move Old Files to New Names...\" first, "
              "then move it to its save folder")
R_EXISTS = "the save's own folder already has one of this name; both are kept and read"
R_TOO_LONG = "its new place's path would be too long for the game, so it stays where it is (still read)"
R_SHARED_LOG = ("an older shared log: records of several saves in one file, and splitting it would "
                "rewrite history (still read)")
R_WORDS = ("the shared Like and Dislike Words: one file for every save (the moved logs' boundaries "
           "are copied into each save's own file instead)")
R_BACKUPS = "a backup: backups are never moved"
R_COPIES = "copies made before repairs: backups are never moved"
R_LOOSE_DATA = ("a loose file in the Data folder itself, an older build's: the game moves it into its "
                "folder itself")
R_LOOSE_SAVE = ("a loose file in the save folder itself, an older build's: the game moves it into its "
                "folder itself")
R_TREES = "Family Trees are named by the player, not by save"
R_NOT_SAVE = "not one save's (no save slot in its name)"

_SAVE = re.compile(r"(?i)save ([1-5])")
_LOOSE = re.compile(r"(?i)^(vv\d?_|vvfp)")
_OLD_DATA_FOLDERS = {old.lower() for old, _new in layout.FOLDERS if old.lower().startswith(layout.DATA.lower() + "\\")}
_OLD_DATA_FOLDERS |= {old.lower() for old, new, _b, _f in layout.FILES if old.lower() != new.lower()}


class MoveError(tools.LogToolError):
    """Nothing was changed, or everything changed was put back; the message says which."""


# ---------------------------------------------------------------------------
# Does the game's patch read the save folders?
# ---------------------------------------------------------------------------


def _bytes_hold(data: bytes, text: str) -> bool:
    return text.encode("ascii") in data or text.encode("utf-16-le") in data


@dataclass
class InstallCheck:
    save_folder: Path
    game_folder: Path | None
    older: list[Path] = field(default_factory=list)     # patch DLLs that know only the older folders

    @property
    def refused(self) -> bool:
        return self.game_folder is None or bool(self.older)

    def message(self) -> str:
        name = self.save_folder.name
        if self.game_folder is None:
            return (f"The game that saves into \"{name}\" was not found (a folder named \"{name}\" holding "
                    f"\"{name}.exe\", beside the original game or in the patcher's output folder), so the "
                    "patcher cannot check that its patch reads the save folders. Choose the game in the "
                    "patcher (or patch it again with this patcher) first. Nothing was changed.")
        dlls = ", ".join(str(p) for p in self.older)
        return (f"{name} was patched by an older patcher: {dlls} look only in the older folders "
                f"(\"{layout.LOGS}\" and \"{layout.DATA}\"), so after the move the game would find its "
                "logs and records missing. Patch the game again with this patcher first, then move the "
                "files. Nothing was changed.")


def check_install(save_folder: Path, game_folders: list[Path]) -> InstallCheck:
    """Every one of `game_folders` that is a game saving into `save_folder` (a folder of the save
    folder's name holding "<name>.exe", as vv_move_old_names.patched_by finds it), and every .dll in
    each or in its "Virtual Villagers Fun Patcher Files" folder that names the older folders but not
    `Virtual Villagers Fun Patcher\\Save ` (ASCII or UTF-16-LE).  The first match is `game_folder`.
    Reads only."""
    save_folder = Path(save_folder)
    name = save_folder.name
    first = None
    older = []
    for folder in game_folders:
        folder = Path(folder)
        if folder.name.casefold() != name.casefold() or not (folder / f"{name}.exe").is_file():
            continue
        first = folder if first is None else first
        for library in sorted(folder.glob("*.dll")) + sorted((folder / PATCH_FILES).glob("*.dll")):
            try:
                data = library.read_bytes()
            except OSError:
                continue
            if any(_bytes_hold(data, n) for n in OLD_LAYOUT_NAMES) and not _bytes_hold(data, NEW_LAYOUT_MARKER):
                older.append(library)
    return InstallCheck(save_folder, first, older)


# ---------------------------------------------------------------------------
# What moves
# ---------------------------------------------------------------------------


@dataclass
class Move:
    slot: int
    old: str            # relative to the save folder
    new: str


@dataclass
class Left:
    what: str           # relative to the save folder ("...\\" for a whole folder)
    reason: str
    slot: int | None = None


@dataclass
class Plan:
    folder: Path
    game: int | None
    moves: list[Move] = field(default_factory=list)
    left: list[Left] = field(default_factory=list)

    def slots(self) -> list[int]:
        return sorted({m.slot for m in self.moves})

    def describe(self) -> str:
        game = f"Virtual Villagers: {GAME_TITLES[self.game]}" if self.game in GAME_TITLES else "This game"
        out = [f"{game}, save folder \"{self.folder.name}\".", ""]
        if self.moves:
            out.append(f"{len(self.moves)} file(s) move into each save's own folder "
                       f"(\"{layout.SAVES}\\Save <n>\"), from where to where:")
            for slot in self.slots():
                mine = [m for m in self.moves if m.slot == slot]
                out += ["", f"Save {slot} ({len(mine)} file(s)):"]
                for m in mine:
                    out += [f"  {m.old}", f"    -> {m.new}"]
        else:
            out.append("Nothing moves: no save's files are left in the older folders.")
        if self.left:
            out += ["", f"Not moved ({len(self.left)}), each with the reason:"]
            for item in self.left:
                where = f"Save {item.slot}: " if item.slot else ""
                out.append(f"  {where}{item.what} -- {item.reason}")
        out += ["", "Each file is copied to \"Copies Made Before Repairs\" first; nothing is deleted until its "
                "new copy is checked, and if anything fails everything is put back. The game's own saves "
                "and the Backups are never touched."]
        return "\n".join(out)


def _rel(folder: Path, path: Path) -> str:
    return str(Path(path).relative_to(folder)).replace("/", "\\")


def _is_link(path: Path) -> bool:
    return vv_save_backup._is_link(path)


def _files_under(root: Path) -> list[Path]:
    out = []
    for entry in sorted(root.iterdir(), key=lambda p: p.name.casefold()):
        if _is_link(entry):
            continue
        if entry.is_dir():
            out += _files_under(entry)
        elif entry.is_file():
            out.append(entry)
    return out


_NAMED_SLOT = re.compile(r"(?i) - Save ([1-5])(?=\.|$)")


def _slot_of(rel: str) -> int | None:
    """The save slot a file's name names (" - Save <S>"), whatever folder it is in."""
    found = _NAMED_SLOT.findall(str(rel).rpartition("\\")[2])
    return int(found[-1]) if found else None


def _old_name(rel: str) -> bool:
    """A Data file still under an older build's name (vv_save_layout FOLDERS / FILES): in one of the
    older folders, or named as an older build named it ("... Village Roster - Save <S>", "... Genealogy
    Edits - Save <S>")."""
    head, _, name = rel.rpartition("\\")
    low = head.lower()
    if any(low == old or low.startswith(old + "\\") for old in _OLD_DATA_FOLDERS):
        return True
    for (old_folder, new_folder, _back, _file), (forward, _template) in zip(layout.FILES, layout.FILES_FORWARD):
        if low in (old_folder.lower(), new_folder.lower()) and forward.match(name):
            return True
    return False


def _candidate(folder: Path, rel: str, plan_: Plan) -> None:
    place = layout.per_save_place(rel)
    if place is None:
        plan_.left.append(Left(rel, R_NOT_SAVE))
        return
    slot, new_rel, _unit = place
    target = folder / new_rel
    if layout._there(target) is not False:
        plan_.left.append(Left(rel, R_EXISTS, slot))
    elif not layout._fits(target):
        plan_.left.append(Left(rel, R_TOO_LONG, slot))
    else:
        plan_.moves.append(Move(slot, rel, new_rel))


def _plan_logs(folder: Path, logs: Path, plan_: Plan) -> None:
    for entry in sorted(logs.iterdir(), key=lambda p: p.name.casefold()):
        if _is_link(entry):
            continue
        if entry.is_file():
            plan_.left.append(Left(_rel(folder, entry), R_NOT_SAVE))
        elif entry.is_dir():
            if _SAVE.fullmatch(entry.name):
                for path in _files_under(entry):
                    _candidate(folder, _rel(folder, path), plan_)
            else:
                for path in _files_under(entry):
                    plan_.left.append(Left(_rel(folder, path), R_SHARED_LOG))


def _plan_data(folder: Path, data: Path, plan_: Plan) -> None:
    for entry in sorted(data.iterdir(), key=lambda p: p.name.casefold()):
        if _is_link(entry):
            continue
        rel = _rel(folder, entry)
        if entry.is_file():
            plan_.left.append(Left(rel, R_LOOSE_DATA, _slot_of(rel)))
            continue
        if not entry.is_dir():
            continue
        low = entry.name.lower()
        if low == layout.COPIES.lower():
            plan_.left.append(Left(rel + "\\", R_COPIES))
            continue
        if low == layout.LOG_WORDS.lower():
            for path in _files_under(entry):
                plan_.left.append(Left(_rel(folder, path), R_WORDS))
            continue
        for path in _files_under(entry):
            prel = _rel(folder, path)
            if _old_name(prel):
                plan_.left.append(Left(prel, R_OLD_NAME, _slot_of(prel)))
            else:
                _candidate(folder, prel, plan_)


def plan(folder: Path) -> Plan:
    """Every file of a save left in the older folders and its place in that save's own folder, and
    everything in the patcher's folders that is not moved, with the reason.  The game's own saves are
    never listed.  Reads only names; nothing is changed."""
    folder = Path(folder)
    out = Plan(folder, vv_save_backup.game_number(folder))
    for entry in sorted(folder.iterdir(), key=lambda p: p.name.casefold()):
        if _is_link(entry):
            continue
        low = entry.name.lower()
        if entry.is_file():
            if entry.suffix.lower() != ".ldw" and _LOOSE.match(entry.name):
                out.left.append(Left(entry.name, R_LOOSE_SAVE, _slot_of(f"{layout.DATA}\\x\\{entry.name}")))
            continue
        if not entry.is_dir():
            continue
        if low == "backups":
            out.left.append(Left(entry.name + "\\", R_BACKUPS))
        elif low == layout.TREES.lower():
            out.left.append(Left(entry.name + "\\", R_TREES))
        elif low == "vvfp logs":
            for path in _files_under(entry):
                out.left.append(Left(_rel(folder, path), R_SHARED_LOG))
        elif low == layout.LOGS.lower():
            _plan_logs(folder, entry, out)
        elif low == layout.DATA.lower():
            _plan_data(folder, entry, out)
    return out


# ---------------------------------------------------------------------------
# Moving
# ---------------------------------------------------------------------------


@dataclass
class MoveResult:
    folder: Path
    moved: list[Move] = field(default_factory=list)
    left: list[Left] = field(default_factory=list)
    copies: dict = field(default_factory=dict)          # old place (relative) -> the copy made first
    removed_folders: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)      # a Repairs Made record that could not be written

    def lines(self) -> list[str]:
        out = [f"Moved: {m.old} -> {m.new}" for m in self.moved]
        out += [f"Empty folder removed: {name}" for name in self.removed_folders]
        out += [f"Not moved: {item.what} ({item.reason})" for item in self.left]
        out += self.notes
        return out


@dataclass
class _State:
    """Everything this run changed, so it can be put back."""
    data: dict = field(default_factory=dict)        # old path -> its bytes as they were
    copies: dict = field(default_factory=dict)      # old path -> its verified copy
    created: list = field(default_factory=list)     # [new path, old path, complete]
    dirs: list = field(default_factory=list)        # folders this run made
    words: dict = field(default_factory=dict)       # words file -> its bytes before (None: not there)
    removed: list = field(default_factory=list)     # originals removed
    step: str = ""


def _refuse_if_running(folder: Path, processes) -> None:
    try:
        tools._refuse_if_running(folder, processes)
    except tools.GameRunning as exc:
        raise tools.GameRunning(str(exc).replace("Repair Saves & Logs never", "Moving files never")) from exc


def _make_dirs(path: Path, state: _State) -> None:
    """`path` made with every missing parent, each remembered so it can be removed again."""
    missing = []
    probe = Path(path)
    while not probe.exists():
        missing.append(probe)
        probe = probe.parent
    for d in reversed(missing):
        d.mkdir()
        state.dirs.append(d)


def _write_new(path: Path, data: bytes) -> None:
    with open(path, "xb") as out:
        out.write(data)
        out.flush()
        os.fsync(out.fileno())


def _copy_place(folder: Path, path: Path) -> Path:
    for k in range(1, 1000):
        candidate = tools.copy_before_repair(folder, path, COPY_SUFFIX + ("" if k == 1 else f"-{k}"))
        if not candidate.exists():
            return candidate
    raise MoveError(f"{path.name} has too many copies already.")


def _back_up_one(folder: Path, old: Path, state: _State) -> None:
    """Step 2: one file copied to Copies Made Before Repairs and read back."""
    data = old.read_bytes()
    state.data[old] = data
    copy = _copy_place(folder, old)
    _make_dirs(copy.parent, state)
    _write_new(copy, data)
    shutil.copystat(old, copy)
    if copy.read_bytes() != data:
        raise OSError(f"the copy of {old.name} did not read back as it was")
    state.copies[old] = copy


def _copy_one(folder: Path, move: Move, state: _State) -> None:
    """Step 3: one file copied to its new place (never replacing anything) and read back."""
    old, new = folder / move.old, folder / move.new
    data = state.data[old]
    _make_dirs(new.parent, state)
    entry = [new, old, False]
    with open(new, "xb") as out:
        state.created.append(entry)                 # this run's own file from here on
        out.write(data)
        out.flush()
        os.fsync(out.fileno())
    shutil.copystat(old, new)
    if new.read_bytes() != data:
        raise OSError(f"the new copy of {old.name} did not read back as it was")
    entry[2] = True


def _boundary(folder: Path, game: int, key: str) -> int | None:
    """The smallest boundary any of the game's words files records for `key` (each file's last line
    naming it counts)."""
    found = None
    for path in layout.words_files(folder, game):
        here = None
        for line in path.read_bytes().decode("utf-8", "replace").splitlines():
            offset, tab, name = line.partition("\t")
            if tab and name.lower() == key.lower():
                try:
                    here = int(offset)
                except ValueError:
                    continue
        if here is not None:
            found = here if found is None else min(found, here)
    return found


def _append_words(path: Path, line: bytes, state: _State) -> None:
    """Step 4: one boundary line appended to a words file (its first state remembered)."""
    if path not in state.words:
        state.words[path] = path.read_bytes() if path.exists() else None
        _make_dirs(path.parent, state)
    with open(path, "ab") as out:
        out.write(line)
        out.flush()
        os.fsync(out.fileno())


def _copy_words(folder: Path, game: int, moves: list[Move], state: _State) -> list[tuple[Path, bytes]]:
    checker = tools.load_checker()
    wanted = []
    for move in moves:
        if not move.old.lower().startswith(layout.LOGS.lower() + "\\"):
            continue
        boundary = _boundary(folder, game, checker.word_key(move.old))
        if boundary is None:
            continue
        key = checker.word_key(move.new)
        wanted.append((layout.words_file_for(folder, game, key), f"{boundary}\t{key}\r\n".encode("utf-8")))
    for path, line in wanted:
        _append_words(path, line, state)
    return wanted


def _remove_original(folder: Path, move: Move, state: _State) -> None:
    """Step 5: the original removed, once its new copy and the original itself still match the copy
    made first (the original is read again here, so a change made after the copy is never deleted)."""
    old, new = folder / move.old, folder / move.new
    if new.read_bytes() != state.copies[old].read_bytes():
        raise OSError(f"the new copy of {old.name} no longer matches the copy made first")
    if old.read_bytes() != state.copies[old].read_bytes():
        raise OSError(f"{old.name} changed after the copy was made, so it is kept")
    old.unlink()
    state.removed.append(old)


def _remove_empty(folder: Path, moves: list[Move], state: _State) -> list[str]:
    """Step 6: the older log folders under "...Logs\\Save <S>\\" that held moved files and are now truly
    empty, deepest first (os.rmdir refuses one that is not)."""
    roots = {}
    for move in moves:
        if not move.old.lower().startswith(layout.LOGS.lower() + "\\"):
            continue
        root = folder / layout.slot_folder(move.slot)
        d = (folder / move.old).parent
        while True:
            roots[d] = True
            if d == root or root not in d.parents:
                break
            d = d.parent
    removed = []
    for d in sorted(roots, key=lambda p: -len(p.parts)):
        if not d.is_dir() or _is_link(d) or any(d.iterdir()):
            continue
        vv_save_backup._clear_read_only(str(d))
        os.rmdir(d)
        removed.append(_rel(folder, d))
    return removed


def copies_folder(copies) -> Path:
    """The folder that holds all of `copies` (the copies made first)."""
    paths = [str(Path(p).parent) for p in copies]
    return Path(os.path.commonpath(paths))


def _put_back(state: _State) -> list[str]:
    """Everything this run changed put back; what could not be, by name."""
    failed = []
    for old in reversed(state.removed):
        copy = state.copies[old]
        try:
            data = copy.read_bytes()
            old.parent.mkdir(parents=True, exist_ok=True)
            _write_new(old, data)
            shutil.copystat(copy, old)
            if old.read_bytes() != data:
                raise OSError("it did not read back")
        except OSError as exc:
            failed.append(f"{old} (its copy is {copy}; {exc})")
    for new, old, complete in reversed(state.created):
        try:
            if complete and old.is_file() and new.read_bytes() != old.read_bytes():
                failed.append(f"{new} was changed after it was made, so it is kept")
                continue
            new.unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:
            failed.append(f"{new} ({exc})")
    for path, before in state.words.items():
        try:
            if before is None:
                path.unlink()
            else:
                with open(path, "r+b") as out:
                    out.truncate(len(before))
                if path.read_bytes() != before:
                    path.write_bytes(before)
        except FileNotFoundError:
            pass
        except OSError as exc:
            failed.append(f"{path} ({exc})")
    for d in reversed(state.dirs):
        try:
            d.rmdir()
        except OSError:
            pass
    return failed


def move_to_save_folders(folder: Path, game_folders: list[Path], processes=None, now: datetime | None = None,
                         *, confirmed: Plan | None = None) -> MoveResult:
    """Move every file of a save left in the older folders into that save's own folder (see the module's
    docstring).  Refused, with nothing changed, while the game is running, when the game is not found
    among `game_folders`, or when its patch reads only the older folders.  With `confirmed` (the plan
    the player saw), only the moves in it that are still to be made are made."""
    folder = Path(folder)
    game = vv_save_backup.game_number(folder)
    if game is None:
        raise MoveError(f"\"{folder.name}\" is not one of the five games' save folders. Nothing was changed.")
    controller = processes if processes is not None else vv_save_backup.WindowsProcesses()
    _refuse_if_running(folder, controller)
    check = check_install(folder, game_folders)
    if check.refused:
        raise MoveError(check.message())
    fresh = plan(folder)
    moves = fresh.moves
    if confirmed is not None:
        agreed = {(m.old.lower(), m.new.lower()) for m in confirmed.moves}
        moves = [m for m in moves if (m.old.lower(), m.new.lower()) in agreed]
    result = MoveResult(folder, left=list(fresh.left))
    if not moves:
        return result
    state = _State()
    try:
        state.step = "copying each file to Copies Made Before Repairs"
        for move in moves:
            _back_up_one(folder, folder / move.old, state)
        state.step = "copying each file to its save's folder"
        for move in moves:
            _copy_one(folder, move, state)
        state.step = "copying the Like and Dislike Words boundaries"
        _copy_words(folder, game, moves, state)
        state.step = "checking the game is still closed"
        _refuse_if_running(folder, controller)
        state.step = "removing the originals"
        for move in moves:
            _remove_original(folder, move, state)
        state.step = "removing the emptied older log folders"
        removed = _remove_empty(folder, moves, state)
    except Exception as exc:
        failed = _put_back(state)
        where = (" These could not be put back: " + "; ".join(failed) + ".") if failed else ""
        copies = f" The copies made first are kept in {copies_folder(state.copies.values())}." if state.copies else ""
        raise MoveError(f"Moving the files to the save folders failed while {state.step} ({exc}). "
                        f"Everything was put back as it was.{where}{copies}") from exc
    result.moved = list(moves)
    result.removed_folders = removed
    result.copies = {m.old: state.copies[folder / m.old] for m in moves}
    for slot in sorted({m.slot for m in moves}):
        try:
            note_move_slot(folder, game, slot, result, now)
        except (OSError, tools.LogToolError) as exc:
            result.notes.append(f"Save {slot}'s Repairs Made log could not be written ({exc})")
    return result


def note_move_slot(folder: Path, game: int, slot: int, result: MoveResult, now: datetime | None = None) -> None:
    """One "Repair <n>" record in the save's own Repairs Made log: every file of that save moved (old ->
    new), every item of that save not moved with its reason, and where the copies made first are; under
    the village's header when its Births log can be read, else "Village: (Save <S>)"."""
    try:
        header = tools.load_checker().births_log(folder, game, slot)[0].village
    except Exception:                       # the header is only the Repairs log's label
        header = None
    if not header or layout.header_slot(header) != slot:
        header = f"Village: (Save {slot})"
    path, text = tools.repair_record_start(folder, game, header, slot, now)
    text += f"  Checked: this save's files in the older folders ({TITLE})\r\n"
    for m in result.moved:
        if m.slot == slot:
            text += f"  Moved: {m.old} -> {m.new}\r\n"
    for item in result.left:
        if item.slot == slot:
            text += f"  Not moved: {item.what} ({item.reason})\r\n"
    for name in result.removed_folders:
        if layout.is_slot_folder(folder / name / "x") == slot:
            text += f"  Empty folder removed: {name}\r\n"
    mine = [copy for old, copy in result.copies.items() if any(m.old == old and m.slot == slot for m in result.moved)]
    if mine:
        text += f"  Copies made first: {_rel(folder, copies_folder(mine))}\r\n"
    text += "\r\n"
    with open(path, "ab") as log:
        log.write(text.encode("latin-1", "replace"))
