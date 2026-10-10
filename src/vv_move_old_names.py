"""Repair Saves & Logs' "Move Old Files to New Names..." (the owner, 2026-10-09: "Repair logs should
have the move legacy files button!").

The patcher never moves a file on its own (src/vv_save_layout.py: a v1.35.64 preview did, while A
New Home was still patched by v1.35.63, which then found its parents "empty").  This is the player's
own button, for one save folder, with the game closed, and only once every game that plays this save
is patched with v1.35.64 or newer (older patches look only under the old names):

  1. what is still under an older build's name, and where it goes, is listed (`plan`) and the
     player is asked first;
  2. the game must be closed; the save folder is backed up with Back Up Saves' own copier
     ("(before repair re-arm)", Repair Saves & Logs' label), and nothing is done when it fails;
  3. an old file or folder whose new name is free is renamed into place (never replacing a file);
     under both names:
       a folder is merged file by file (a file the new folder lacks is moved in);
       a Deaths or Repairs log in both: the new file's records, then the old file's records not
         already in the new folder (the same identity scripts/vvfp_consistency_check.py
         deaths_records uses), written through a temporary file; when that would change what the
         logs show, both are left where they are, and the report says so;
       the Like and Dislike Words in both: the smaller boundary of each log file;
       a Repair approval in both: the game acts on neither, so neither is kept under the new name;
       any other file: the one written last (vv_save_layout.find's choice) under the new name;
     whatever is superseded goes to "Data\\Copies Made Before Repairs\\<its own place>" -- nothing
     is deleted, but an old folder left truly empty;
  4. what was done is listed, and written as one record in the Repairs Made log.

Backups, Tribe History and Tribe Population, and everything outside the patcher's own folders, are
never touched.  On an error it stops at once and says what was already moved."""
from __future__ import annotations

import os
import re
import shutil
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import vv_log_tools as tools
import vv_save_backup
import vv_save_layout as layout

BACKUP_LABEL = vv_save_backup.BEFORE_REARM    # Repair Saves & Logs' own label, listed by Restore Saves
FIRST_VERSION = (1, 35, 64)          # the first patcher whose games read the new names
TRANSPARENCY = ("Virtual Villagers Fun Patcher Files\\VVFP Transparency Log.txt", "VVFP Transparency Log.txt")
_VERSION = re.compile(r"^Patcher version/commit: v(\d+)\.(\d+)\.(\d+)", re.M)
# Names only a game patched with v1.35.64 or newer carries (native/shared/save_layout.h), and names
# every older patch carries.
_NEW_NAMES = ("Deaths and Disappearances", "Parents (A New Home)", "Like and Dislike Words")
_OLD_NAMES = ("Parentage Records", "Cross-Check", "Log Words")

_LOG_FOLDERS = {f"{layout.LOGS}\\Deaths".lower(): "Death ", f"{layout.LOGS}\\Repairs".lower(): "Repair "}
_APPROVAL = re.compile(r"^Virtual Villagers \d Repair Approved - Save \d+\.dat$", re.I)
_WORDS = re.compile(r"^Virtual Villagers \d Log Words\.dat$", re.I)
_DEATHS_LOG = re.compile(r"^Virtual Villagers (\d) Deaths Log \d+\.txt$", re.I)


class MoveError(tools.LogToolError):
    """Nothing more was done; the message says what was."""


# ---------------------------------------------------------------------------
# Which version patched the game
# ---------------------------------------------------------------------------


@dataclass
class PatchedBy:
    game_folder: Path | None
    version: tuple[int, int, int] | None     # from the game's transparency report
    old_layout: bool = False                 # no report, and its patch files know only the old names

    @property
    def refused(self) -> bool:
        return (self.version is not None and self.version < FIRST_VERSION) or (
            self.version is None and self.old_layout)

    def describe(self) -> str:
        if self.version is not None:
            return "v" + ".".join(map(str, self.version))
        return "an older patcher" if self.old_layout else "unknown"


def _bytes_hold(data: bytes, name: str) -> bool:
    return name.encode("ascii") in data or name.encode("utf-16-le") in data


def patched_by(save_folder: Path, game_folders: list[Path]) -> PatchedBy:
    """The patcher version that built the game saving into `save_folder`, from the first of
    `game_folders` that is that game (a folder of the save folder's name holding "<name>.exe"):
    its transparency report, or else whether its patch files know the new names at all."""
    name = Path(save_folder).name
    for folder in game_folders:
        folder = Path(folder)
        if folder.name.casefold() != name.casefold() or not (folder / f"{name}.exe").is_file():
            continue
        for report in TRANSPARENCY:
            try:
                match = _VERSION.search((folder / report).read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
            if match:
                return PatchedBy(folder, tuple(int(g) for g in match.groups()))
        new = old = False
        for library in list(folder.glob("*.dll")) + list((folder / "Virtual Villagers Fun Patcher Files").glob("*.dll")):
            try:
                data = library.read_bytes()
            except OSError:
                continue
            new = new or any(_bytes_hold(data, n) for n in _NEW_NAMES)
            old = old or any(_bytes_hold(data, n) for n in _OLD_NAMES)
        return PatchedBy(folder, None, old and not new)
    return PatchedBy(None, None)


# ---------------------------------------------------------------------------
# What is under an older name
# ---------------------------------------------------------------------------


@dataclass
class Item:
    kind: str           # "move", "combine log", "combine words", "keep newest", "approval both", "remove empty"
    old: str            # relative to the save folder
    new: str
    folder: bool = False

    def describe(self) -> str:
        if self.kind == "remove empty":
            return f"{self.old}  ->  an empty folder, removed"
        what = {
            "move": "moved to",
            "combine log": "records not already there added to",
            "combine words": "boundaries combined (the smaller of each) into",
            "keep newest": "the one written last kept as",
            "approval both": "under both names: neither is kept as",
        }[self.kind]
        return f"{self.old}  ->  {what}  {self.new}"


def _rel(folder: Path, path: Path) -> str:
    return str(path.relative_to(folder)).replace("/", "\\")


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


def _classify(folder: Path, old: Path, new: Path) -> str:
    """How a file under both names is handled."""
    parent = _rel(folder, old.parent).lower()
    if parent in _LOG_FOLDERS and old.suffix.lower() == ".txt":
        return "combine log"
    if _WORDS.match(old.name) and parent == f"{layout.DATA}\\Log Words".lower():
        return "combine words"
    if _APPROVAL.match(old.name):
        return "approval both"
    return "keep newest"


def plan(folder: Path) -> list[Item]:
    """Everything still under an older build's name in the save folder, and where it goes.  Reads
    only names; nothing is changed."""
    folder = Path(folder)
    items: list[Item] = []
    for old_rel, new_rel in layout.FOLDERS:
        old, new = folder / old_rel, folder / new_rel
        if not old.is_dir() or _is_link(old):
            continue
        if not new.exists():
            items.append(Item("move", old_rel, new_rel, folder=True))
            continue
        if not new.is_dir():
            continue
        if not _files_under(old):
            items.append(Item("remove empty", old_rel, "", folder=True))
        for path in _files_under(old):
            inner = _rel(old, path)
            target = new / inner
            new_file = f"{new_rel}\\{inner}"
            if not target.exists():
                items.append(Item("move", _rel(folder, path), new_file))
            elif target.is_file():
                items.append(Item(_classify(folder, path, target), _rel(folder, path), new_file))
    for index, (old_folder, new_folder, _back, _old_file) in enumerate(layout.FILES):
        where = folder / old_folder
        if not where.is_dir() or _is_link(where):
            continue
        if old_folder != new_folder and not _files_under(where):
            items.append(Item("remove empty", old_folder, "", folder=True))
        for path in sorted(where.iterdir(), key=lambda p: p.name.casefold()):
            if not path.is_file() or _is_link(path):
                continue
            name = layout.new_file_name(index, path.name)
            if name is None:
                continue
            new_file = f"{new_folder}\\{name}"
            target = folder / new_file
            if not target.exists():
                items.append(Item("move", _rel(folder, path), new_file))
            elif target.is_file():
                items.append(Item("keep newest", _rel(folder, path), new_file))
    return items


# ---------------------------------------------------------------------------
# Combining what both names hold
# ---------------------------------------------------------------------------


def _blocks(text: str) -> list[tuple[str | None, str]]:
    """A numbered log's records, as scripts/vvfp_consistency_check.py numbered_records reads them:
    (its "Village:" header, its lines) for every block between blank lines."""
    out, header = [], None
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n")):
        lines = [line for line in block.split("\n") if line.strip()]
        heads = [line for line in lines if line.startswith("Village:")]
        if heads:
            header = heads[-1].rstrip()
            lines = [line for line in lines if not line.startswith("Village:")]
        if lines:
            out.append((header, "\n".join(lines)))
    return out


def _read(path: Path) -> str:
    return path.read_bytes().decode("latin-1")


def combined_log(new_text: str, old_text: str, present: Counter) -> tuple[str, int]:
    """The new log, then the old log's records not in `present` (the new folder's records, a
    multiset, used up as they match); and how many were added.  The new log's bytes are kept as
    they are, so every boundary recorded for it still holds."""
    eol = "\r\n" if "\r\n" in new_text or "\r\n" in old_text or not new_text else "\n"
    out = new_text
    heads = [line.rstrip() for line in new_text.replace("\r\n", "\n").split("\n") if line.startswith("Village:")]
    header = heads[-1] if heads else None
    added = 0
    for head, block in _blocks(old_text):
        if present[(head, block)] > 0:
            present[(head, block)] -= 1
            continue
        if out and not out.endswith("\n"):
            out += eol
        if out and not out.endswith(eol + eol) and not out.endswith("\n\n"):
            out += eol
        if head is not None and head != header:
            out += head + eol
            header = head
        out += block.replace("\n", eol) + eol + eol
        added += 1
    return out, added


def _all_records(root: Path) -> Counter:
    found: Counter = Counter()
    if root.is_dir():
        for path in sorted(root.glob("*.txt")):
            found.update(_blocks(_read(path)))
    return found


def _deaths_view(root: Path, games: set[int]) -> dict:
    checker = tools.load_checker()
    return {(game, slot): sorted(checker.deaths_records(root, game, slot)) for game in games for slot in range(1, 6)}


def _word_lines(path: Path) -> dict[str, tuple[str, int]]:
    """lower-case name -> (name, boundary): the last line naming it."""
    out: dict[str, tuple[str, int]] = {}
    for line in path.read_bytes().decode("utf-8", "replace").splitlines():
        offset, tab, name = line.partition("\t")
        if tab and name:
            try:
                out[name.lower()] = (name, int(offset))
            except ValueError:
                continue
    return out


def combined_words(first: Path, second: Path | None, lower: dict[str, int]) -> bytes:
    """One Like and Dislike Words file from one or two: the smaller boundary of each log file, and
    no larger than `lower` says (a Deaths log that had records added after its own end)."""
    merged: dict[str, tuple[str, int]] = {}
    for path in [p for p in (first, second) if p is not None]:
        for key, (name, offset) in _word_lines(path).items():
            merged[key] = (merged[key][0], min(offset, merged[key][1])) if key in merged else (name, offset)
    for key, limit in lower.items():
        if key in merged and merged[key][1] > limit:
            merged[key] = (merged[key][0], limit)
    return "".join(f"{offset}\t{name}\r\n" for name, offset in merged.values()).encode("utf-8")


# ---------------------------------------------------------------------------
# Moving
# ---------------------------------------------------------------------------


@dataclass
class MoveResult:
    folder: Path
    backup: vv_save_backup.BackupResult | None
    moved: list[str] = field(default_factory=list)
    combined: list[str] = field(default_factory=list)
    set_aside: list[str] = field(default_factory=list)
    left: list[str] = field(default_factory=list)      # left under both names, and why
    removed: list[str] = field(default_factory=list)   # empty old folders removed

    def lines(self) -> list[str]:
        out = [f"Moved: {line}" for line in self.moved]
        out += [f"Combined: {line}" for line in self.combined]
        out += [f"Set aside: {line}" for line in self.set_aside]
        out += [f"Left as it was: {line}" for line in self.left]
        out += [f"Empty folder removed: {line}" for line in self.removed]
        return out


def _copy_place(folder: Path, path: Path) -> Path:
    """Where `path` is set aside: Data\\Copies Made Before Repairs\\<its own place>, " (2)" ... when
    taken."""
    target = tools.copy_before_repair(folder, path, "")
    k = 2
    while target.exists():
        base = tools.copy_before_repair(folder, path, "")
        target = base.with_name(f"{base.stem} ({k}){base.suffix}")
        k += 1
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def _rename(source: Path, target: Path) -> None:
    """A same-volume rename that never replaces anything (os.rename refuses an existing target on
    Windows; checked here too)."""
    if target.exists():
        raise FileExistsError(f"{target} already exists")
    target.parent.mkdir(parents=True, exist_ok=True)
    os.rename(source, target)


def _write_atomic(path: Path, data: bytes) -> None:
    temporary = path.with_name(path.name + ".move-tmp")
    try:
        with open(temporary, "xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise


def _set_aside(folder: Path, path: Path, result: MoveResult, copy: bool = False) -> None:
    target = _copy_place(folder, path)
    if copy:
        with open(path, "rb") as source, open(target, "xb") as out:
            shutil.copyfileobj(source, out)
        shutil.copystat(path, target)
    else:
        _rename(path, target)
    result.set_aside.append(f"{_rel(folder, path)} -> {_rel(folder, target)}")


def _refuse_if_running(folder: Path, processes) -> None:
    try:
        tools._refuse_if_running(folder, processes)
    except tools.GameRunning as exc:
        raise tools.GameRunning(str(exc).replace("Repair Saves & Logs never", "Moving old files never")) from exc


def move_old_files(folder: Path, processes: vv_save_backup.ProcessController | None = None,
                   now: datetime | None = None, *, patched: PatchedBy | None = None) -> MoveResult:
    """Move everything under an older build's name to its new name (see the module's docstring).
    Refused while the game is running, or when `patched` says the game was built by a patcher older
    than v1.35.64; the save folder is backed up first."""
    folder = Path(folder)
    if patched is not None and patched.refused:
        raise MoveError(refusal(patched))
    controller = processes if processes is not None else vv_save_backup.WindowsProcesses()
    _refuse_if_running(folder, controller)
    items = plan(folder)
    result = MoveResult(folder, None)
    if not items:
        return result
    try:
        backup = vv_save_backup.copy_save_folder(folder, now or datetime.now(), suffix=BACKUP_LABEL)
    except vv_save_backup.BackupError as exc:
        raise MoveError(f"The backup failed, so nothing was moved. {exc}") from exc
    result.backup = backup
    _refuse_if_running(folder, controller)
    try:
        _carry_out(folder, items, result)
        _remove_empty(folder, result)
    except (OSError, MoveError, tools.LogToolError) as exc:
        done = "\n".join(result.lines()) or "Nothing had been moved yet."
        raise MoveError(f"Moving stopped: {exc}\n\nDone before it stopped:\n{done}\n\n"
                        f"The backup is in {backup.backup_folder}.") from exc
    game = vv_save_backup.game_number(folder)
    if game is not None:
        try:
            note_move(folder, game, result, now)
        except OSError as exc:
            result.left.append(f"the Repairs Made log could not be written ({exc})")
    return result


def refusal(patched: PatchedBy) -> str:
    return (f"{patched.game_folder.name if patched.game_folder else 'This game'} was patched by "
            f"{patched.describe()}, which looks only under the old names: after moving, it would find "
            "its logs and records missing. Patch the game again with this patcher (v1.35.64 or newer) "
            "first, then move the old files. Nothing was changed.")


def _carry_out(folder: Path, items: list[Item], result: MoveResult) -> None:
    games = {int(m.group(1)) for item in items for m in [_DEATHS_LOG.match(Path(item.old).name)] if m}
    lower: dict[str, int] = {}
    # The log folders under both names first, each as a whole: what they add may lower a log file's
    # boundary in the Like and Dislike Words.
    by_folder: dict[str, list[Item]] = {}
    for item in items:
        parent = str(Path(item.old).parent).lower()
        if not item.folder and parent in _LOG_FOLDERS:
            by_folder.setdefault(parent, []).append(item)
    done = set()
    for group in by_folder.values():
        _merge_log_folder(folder, group, games, lower, result)      # all of it, or none of it
        done.update(id(item) for item in group)
    for item in items:
        old, new = folder / item.old, folder / item.new
        if id(item) in done or item.kind == "remove empty" or not old.exists():
            continue
        if item.kind == "move":
            _rename(old, new)
            result.moved.append(f"{item.old} -> {item.new}")
        elif item.kind == "approval both":
            _set_aside(folder, old, result)
            _set_aside(folder, new, result)
            result.left.append(f"{item.new}: a Repair approval was under both names, and the game acts on "
                               "neither, so neither is kept; choose Repair Saves & Logs again to approve one")
        elif item.kind == "combine words":
            data = combined_words(new, old, lower)
            _set_aside(folder, new, result, copy=True)
            _write_atomic(new, data)
            _set_aside(folder, old, result)
            result.combined.append(f"{item.old} + {item.new} (the smaller boundary of each log file)")
            lower = {}
        else:
            _keep_newest(folder, item, result)
    if lower:
        # A Deaths log had records added and the words file was under one name only: lowered there.
        for game in sorted(games):
            words = layout.find(folder, tools.load_checker().LOG_WORDS.format(game=game))
            if words.is_file():
                data = combined_words(words, None, lower)
                if data != words.read_bytes():
                    _set_aside(folder, words, result, copy=True)
                    _write_atomic(words, data)
                    result.combined.append(f"{_rel(folder, words)} (a Deaths log's boundary lowered to the "
                                           "end of its own records)")


def _keep_newest(folder: Path, item: Item, result: MoveResult) -> None:
    """A whole file under both names: the one written last (vv_save_layout.find's choice) under the
    new name, the other set aside."""
    old, new = folder / item.old, folder / item.new
    if layout._written(old) > layout._written(new):
        _set_aside(folder, new, result)
        _rename(old, new)
        result.moved.append(f"{item.old} -> {item.new} (written last; the other set aside)")
    else:
        _set_aside(folder, old, result)
        result.combined.append(f"{item.new} kept (written last)")


def _merge_log_folder(folder: Path, group: list[Item], games: set[int], lower: dict[str, int],
                      result: MoveResult) -> bool:
    """An older build's Deaths (or Repairs) folder emptied into the new one: every log the new one
    lacks moved in, every log in both combined.  The new folder as it would then be is staged first
    and read back: unless it shows every record the two show now -- for the Deaths logs, exactly
    what scripts/vvfp_consistency_check.py deaths_records shows for every save -- nothing in the
    group is touched and both folders stay as they are (the patcher reads both)."""
    checker = tools.load_checker()
    new_dir = (folder / group[0].new).parent
    present = _all_records(new_dir)
    texts = {}
    for item in group:
        if item.kind == "combine log":
            old, new = folder / item.old, folder / item.new
            new_text = _read(new)
            texts[id(item)] = (new_text,) + combined_log(new_text, _read(old), present)
    with tempfile.TemporaryDirectory() as stage:
        staged = Path(stage) / layout.LOGS / new_dir.name
        staged.mkdir(parents=True)
        for path in new_dir.glob("*.txt"):
            shutil.copyfile(path, staged / path.name)
        expect = _all_records(new_dir)
        for item in group:
            old, new = folder / item.old, folder / item.new
            if Path(item.new).parent != Path(group[0].new).parent or old.suffix.lower() != ".txt":
                continue
            if item.kind == "combine log":
                (staged / new.name).write_bytes(texts[id(item)][1].encode("latin-1"))
            elif item.kind == "move":
                shutil.copyfile(old, staged / new.name)
            expect.update(_blocks(_read(old)))
        got = _all_records(staged)
        same = not (set(expect) - set(got)) and all(got[k] >= v for k, v in _all_records(new_dir).items())
        if same and new_dir.name == layout.DEATHS_LOGS and games:
            same = _deaths_view(Path(stage), games) == _deaths_view(folder, games)
    if not same:
        old_dir = Path(group[0].old).parent
        result.left.append(f"{old_dir}: putting its logs into {Path(group[0].new).parent} would change what the "
                           "logs show, so both folders were left as they are (the patcher reads both)")
        return False
    for item in group:
        old, new = folder / item.old, folder / item.new
        if item.kind == "move":
            _rename(old, new)
            result.moved.append(f"{item.old} -> {item.new}")
        elif item.kind == "combine log":
            new_text, text, added = texts[id(item)]
            if added:
                key = checker.word_key(_rel(folder, new)).lower()
                size = len(new_text.encode("latin-1"))
                lower[key] = min(size, lower.get(key, size))
                _set_aside(folder, new, result, copy=True)
                _write_atomic(new, text.encode("latin-1"))
            _set_aside(folder, old, result)
            result.combined.append(f"{item.old} + {item.new} ({added} record(s) added)")
        else:
            _keep_newest(folder, item, result)
    return True


def _remove_empty(folder: Path, result: MoveResult) -> None:
    """An older build's folder left truly empty is removed (os.rmdir refuses one that is not)."""
    olds = [old for old, _new in layout.FOLDERS] + [old for old, new, _b, _f in layout.FILES if old != new]
    for old_rel in olds:
        old = folder / old_rel
        if not old.is_dir() or _is_link(old):
            continue
        if _files_under(old):
            continue
        for path in sorted((p for p in old.rglob("*") if p.is_dir()), key=lambda p: -len(p.parts)) + [old]:
            if _is_link(path) or any(path.iterdir()):
                break
            try:
                # A folder Windows (or OneDrive) marks read-only refuses to be removed even empty.
                vv_save_backup._clear_read_only(str(path))
                path.rmdir()
            except OSError as exc:
                result.left.append(f"{_rel(folder, path)}: an empty folder that could not be removed ({exc.strerror or exc})")
                break
        else:
            result.removed.append(old_rel)


def note_move(folder: Path, game: int, result: MoveResult, now: datetime | None = None) -> None:
    """One "Repair <n>" record in the Repairs Made log, the shape src/vv_log_tools.py note_word_repair
    and native/shared/repairs_log.h write."""
    lines = result.lines()
    if not lines:
        return
    logs = layout.find(folder, f"{layout.LOGS}\\{layout.REPAIRS_LOGS}")
    logs.mkdir(parents=True, exist_ok=True)
    number = 1
    while (logs / f"Virtual Villagers {game} Repairs Log {number + 1}.txt").exists():
        number += 1
    path = logs / f"Virtual Villagers {game} Repairs Log {number}.txt"
    existing = path.read_bytes().decode("latin-1") if path.exists() else ""
    repairs = sum(line.startswith("Repair ") for line in existing.splitlines())
    if repairs >= 256 or len(existing) >= 4 * 1024 * 1024:
        path = logs / f"Virtual Villagers {game} Repairs Log {number + 1}.txt"
        existing, repairs = "", 0
    header = "Village: (all villages in this save folder)"
    last = [line for line in existing.splitlines() if line.startswith("Village:")]
    when = (now or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
    text = "" if last and last[-1].rstrip() == header else header + "\r\n"
    text += f"Repair {repairs + 1}\r\n  Date: {when}\r\n"
    text += "  Checked: the patcher's files kept under older builds' names (Move Old Files to New Names)\r\n"
    for line in lines:
        text += f"  {line}\r\n"
    if result.backup is not None:
        text += f"  Backup: {result.backup.backup_folder.name}\r\n"
    text += "\r\n"
    with open(path, "ab") as log:
        log.write(text.encode("latin-1", "replace"))
