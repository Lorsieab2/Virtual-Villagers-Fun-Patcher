"""Rename Tribe: change a tribe's name inside a closed game's saves.

The owner's request: "a 'Rename Tribe' feature ... Just renames the savefile
internally. (Conforming to the natural character limit)".

Where the name lives (measured on the owner's saves, read-only, and in the
five stock executables -- see docs/rename-tribe.md for the evidence table)
    * The slot save "<base><slot>.ldw" is a small file header ("ldwg", the
      buffer length) and the save buffer. The name is a NUL-terminated ASCII
      string at a fixed buffer offset, the same one the patcher's own log
      headers read (native/shared/village_identity.c).
    * The game also keeps two older generations of each slot,
      "<base>2<slot>.ldw" and "<base>4<slot>.ldw" (its writer rotates slot ->
      slot+20 before every save). The game never reads them back, but they
      are the same village, so a generation still holding the old name is
      renamed too and one holding anything else is left alone.
    * The slot list "<base>0.ldw" keeps the five names as fixed-width fields
      (33 bytes in A New Home and The Lost Children, 21 in the later three).
      At startup the game refills it from the saves, so it is a cache; it is
      updated too, so the two never disagree.
    Only the name bytes change, and the rest of the name field is zeroed. The
    loader checks nothing but the "ldwg" magic and the length: there is no
    checksum, and the save name is never compared with the slot list.

The limit
    The games' name entry lets you type 32 characters (A New Home and The
    Lost Children) or 20 (the later three), and then stores the text with
    GetText(buffer, 32 or 20), which keeps one character fewer: every name a
    game itself makes is at most 31 or 19 characters. That is the limit here,
    and it also keeps clear of the 24-byte copy the later games make of the
    name when a village restarts. Only printable ASCII reaches the entry,
    and A New Home's and The Lost Children's font cannot draw
    # $ % & ( ) * + ; < = > @ [ \\ ] ^ _ { } | ~ (it draws an "A"), so those
    are refused there. Spaces are kept as typed, as the games keep them. A
    name that breaks the rule is refused -- never truncated.

Safety
    * The game must be closed: a running game rewrites its save when it quits,
      which would put the old name straight back (and could clash with the
      write). Nothing here ever closes or pauses a game.
    * Before anything is written the whole save folder is backed up with Back
      Up Saves' own copier, labelled "(before rename)".
    * Every file is written to a temporary file beside it and swapped in with
      os.replace, then read back and compared. Any failure puts every file
      already changed back exactly as it was.

The patcher's logs
    Several logs are bound to their village by the header the exporter wrote,
    "Village: <name> (Save <n>)". Old records are never rewritten, so their
    headers stay as they are; instead one line is appended to each of the
    village's logs:

        Tribe renamed from <old> to <new> on YYYY-MM-DD

    The exporters and Start Over follow such lines (native/shared/
    village_rename.h), so the renamed village keeps its logs: no new log file,
    no rollover, and Start Over still clears them. The statistics, stews,
    elders, roster and graves .dat files are addressed by slot and by roster,
    never by name, so a rename leaves them exactly as they are.

Nothing here touches Tk; the GUI runs it on a worker thread, and the tests
drive it against a throwaway Documents folder and a fake process list.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import vv_save_backup

MAGIC = b"ldwg"
BACKUP_LABEL = vv_save_backup.BEFORE_RENAME
# The slot-select screen's word for an empty slot.
EMPTY_SLOT = "NEW PLAYER"
SLOTS = (1, 2, 3, 4, 5)
# The older generations the game keeps of each slot: "<base>2<slot>.ldw" and
# "<base>4<slot>.ldw".
GENERATIONS = ("2", "4")
LOGS_FOLDER = "Virtual Villagers Fun Patcher Logs"
LEGACY_LOGS_FOLDER = "VVFP Logs"
RENAME_PREFIX = "Tribe renamed from "


class RenameError(Exception):
    """A rename that was refused or failed, with a reason a player can read."""


class GameRunning(RenameError):
    """The game that uses this save folder is running."""


@dataclass(frozen=True)
class GameSaves:
    """One game's save layout and its name-entry limit."""

    number: int
    title: str
    base: str                       # the save file name before the slot number
    name_offset: int                # the name's offset in the save buffer
    buffers: tuple[int, ...]        # every save buffer length the game writes
    headers: tuple[int, ...]        # the file header sizes its saves use
    index_header: int               # the slot index's file header size
    index_first: int                # file offset of slot 1's name in the index
    index_stride: int               # bytes per name in the index
    max_length: int                 # the most characters the game lets you type
    save_field: int                 # bytes reserved for the name in the save buffer

    def index_offset(self, slot: int) -> int:
        return self.index_first + self.index_stride * (slot - 1)

    def save_path(self, folder: Path, slot: int) -> Path:
        return folder / f"{self.base}{slot}.ldw"

    def generation_path(self, folder: Path, generation: str, slot: int) -> Path:
        return folder / f"{self.base}{generation}{slot}.ldw"

    def index_path(self, folder: Path) -> Path:
        return folder / f"{self.base}0.ldw"


GAMES: tuple[GameSaves, ...] = (
    GameSaves(
        1, "Virtual Villagers - A New Home", "Virtual Villagers",
        0x8, (0x0ABDC,), (12,), 12, 22, 33, 31, 33,
    ),
    GameSaves(
        2, "Virtual Villagers - The Lost Children",
        "Virtual Villagers - The Lost Children",
        0x8, (0x30370,), (12,), 12, 22, 33, 31, 33,
    ),
    # The 256 Villagers (Experimental) builds write a longer buffer -- the
    # stock bytes unchanged, then villagers 150..255 -- so the name is at the
    # same offset in either.
    GameSaves(
        3, "Virtual Villagers - The Secret City",
        "Virtual Villagers - The Secret City",
        0x12ECC, (0x12F1C, 0x1A4B4), (12,), 12, 22, 21, 19, 21,
    ),
    # Saves made by older releases of The Tree of Life have a 12-byte header;
    # current ones 24.
    GameSaves(
        4, "Virtual Villagers - The Tree of Life",
        "Virtual Villagers - The Tree of Life",
        0x170B8, (0x1710C, 0x1DCB4), (24, 12), 24, 34, 21, 19, 21,
    ),
    GameSaves(
        5, "Virtual Villagers - New Believers",
        "Virtual Villagers - New Believers",
        0x17D14, (0x17D78, 0x1F168), (24,), 24, 34, 21, 19, 21,
    ),
)


def game_for_title(title: str) -> GameSaves:
    for game in GAMES:
        if game.title.casefold() == title.casefold():
            return game
    raise RenameError(f"Unknown game: {title}")


# ---------------------------------------------------------------------------
# The name rule
# ---------------------------------------------------------------------------

# What the games' text entry accepts. Its key filter takes 0x20..0xFF, but
# the SDL text handler in front of it passes only single-byte input, so what
# reaches a name is printable ASCII (A New Home 0x403B9B, The Lost Children
# 0x403E3B, The Secret City 0x40445B, The Tree of Life 0x404A3B, New
# Believers 0x4049CB).
PRINTABLE = frozenset(chr(code) for code in range(0x20, 0x7F))
# A New Home's and The Lost Children's font has no glyph for these; the game
# draws each of them as an "A". The later three draw all of printable ASCII.
UNDRAWABLE_VV1_VV2 = frozenset("#$%&()*+;<=>@[\\]^_{}|~")


def allowed_characters(game: GameSaves) -> frozenset[str]:
    if game.number in (1, 2):
        return PRINTABLE - UNDRAWABLE_VV1_VV2
    return PRINTABLE


def name_problem(game: GameSaves, name: str) -> str | None:
    """Why ``name`` cannot be a tribe name in ``game``, or None if it can.

    The rule is the game's own: at most ``max_length`` characters (what its
    name entry stores), characters it accepts and can draw, and never empty.
    Spaces are kept as typed, as the game keeps them, but a name of nothing
    but spaces is refused: it would show as a blank slot.
    """
    if not name:
        return "Type a name."
    short = game.title.removeprefix("Virtual Villagers - ")
    bad = sorted({ch for ch in name if ch not in allowed_characters(game)})
    if bad:
        shown = " ".join(repr(ch) for ch in bad)
        return f"{short} cannot use these characters in a name: {shown}."
    if len(name) > game.max_length:
        return f"{len(name)} characters is too long: {short} allows at most {game.max_length}."
    if not name.strip(" "):
        return "A name cannot be only spaces."
    if name == EMPTY_SLOT:
        return f'"{EMPTY_SLOT}" is how the game marks an empty slot.'
    return None


# ---------------------------------------------------------------------------
# Reading the saves
# ---------------------------------------------------------------------------


def _read_c_string(data: bytes, offset: int, width: int) -> str | None:
    """The NUL-terminated printable-ASCII string at ``offset``, or None."""
    raw = data[offset:offset + width]
    end = raw.find(b"\0")
    if end < 0:
        return None
    text = raw[:end]
    if any(byte < 0x20 or byte > 0x7E for byte in text):
        return None
    return text.decode("ascii")


def _save_layout(game: GameSaves, data: bytes) -> tuple[int, int] | None:
    """(header size, buffer length) when ``data`` is one of ``game``'s saves."""
    if data[:4] != MAGIC:
        return None
    for header in game.headers:
        length_at = 8 if header == 12 else 16
        if len(data) < header:
            continue
        length = int.from_bytes(data[length_at:length_at + 4], "little")
        if length in game.buffers and len(data) == header + length:
            return header, length
    return None


def save_name(game: GameSaves, data: bytes) -> str | None:
    """The tribe name in a slot save's bytes, or None if they are not a save."""
    layout = _save_layout(game, data)
    if layout is None:
        return None
    header, _length = layout
    return _read_c_string(data, header + game.name_offset, game.save_field)


def _index_ok(game: GameSaves, data: bytes) -> bool:
    if data[:4] != MAGIC or len(data) < game.index_header:
        return False
    length_at = 8 if game.index_header == 12 else 16
    length = int.from_bytes(data[length_at:length_at + 4], "little")
    return (
        len(data) == game.index_header + length
        and game.index_offset(5) + game.index_stride <= len(data)
    )


def index_name(game: GameSaves, data: bytes, slot: int) -> str | None:
    if not _index_ok(game, data):
        return None
    return _read_c_string(data, game.index_offset(slot), game.index_stride)


@dataclass
class SlotInfo:
    slot: int
    name: str | None            # the name in the slot's save, or None
    problem: str | None = None  # why it cannot be renamed, if it cannot

    @property
    def label(self) -> str:
        if self.name is None:
            return f"Save {self.slot}: (empty)"
        return f"Save {self.slot}: {self.name}"


def read_slots(game: GameSaves, folder: Path) -> list[SlotInfo]:
    """Each slot's tribe name, from its save.

    That is what the slot-select screen shows: at startup every game loads
    each slot's save and copies its name into the slot list (A New Home
    0x41D260, The Lost Children 0x426410, The Secret City 0x4285E0), so the
    list's own names are only a cache of the saves'.
    """
    try:
        index = game.index_path(folder).read_bytes()
    except OSError:
        index = b""
    index_ok = bool(index) and index_name(game, index, 1) is not None
    slots: list[SlotInfo] = []
    for slot in SLOTS:
        path = game.save_path(folder, slot)
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            slots.append(SlotInfo(slot, None, "This slot has no tribe."))
            continue
        except OSError as exc:
            slots.append(SlotInfo(slot, None, f"The save could not be read: {exc}"))
            continue
        name = save_name(game, data)
        info = SlotInfo(slot, name)
        if name is None:
            info.problem = f"{path.name} is not a {game.title} save this tool can read."
        elif not index_ok:
            info.problem = f"The slot list file {game.index_path(folder).name} could not be read."
        slots.append(info)
    return slots


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------


def _with_name(data: bytes, offset: int, width: int, name: str) -> bytes:
    """``data`` with the field at ``offset`` holding ``name``, NUL-padded."""
    encoded = name.encode("ascii")
    if len(encoded) + 1 > width:
        raise RenameError(f"{name!r} does not fit a {width}-byte name field.")
    field = encoded + b"\0" * (width - len(encoded))
    return data[:offset] + field + data[offset + width:]


def _write_atomically(path: Path, data: bytes) -> None:
    """Replace ``path`` with ``data`` through a temporary file, then verify."""
    temporary = path.with_name(path.name + ".rename-tmp")
    try:
        with temporary.open("xb") as handle:
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
    if path.read_bytes() != data:
        raise RenameError(f"{path.name} did not read back as written.")


# ---------------------------------------------------------------------------
# The logs
# ---------------------------------------------------------------------------


def village_header(name: str, slot: int) -> str:
    """The header the exporters write: native/shared/village_identity.c."""
    return f"Village: {name} (Save {slot})"


def rename_note(old: str, new: str, when: datetime) -> str:
    return f"{RENAME_PREFIX}{old} to {new} on {when.strftime('%Y-%m-%d')}"


_DATE_TAIL = re.compile(r" on \d{4}-\d{2}-\d{2}$")


def apply_rename_note(header: str, line: str) -> str:
    """The header ``line`` turns ``header`` into, mirroring village_rename.h.

    "Tribe renamed from <name> to <new> on YYYY-MM-DD" for the header's own
    <name> makes it "Village: <new>" with the same " (Save <n>)"; any other
    line leaves it as it is.
    """
    if not line.startswith(RENAME_PREFIX) or not header.startswith("Village: "):
        return header
    name = header[len("Village: "):]
    suffix = ""
    marker = name.rfind(" (Save ")
    if marker >= 0 and re.fullmatch(r" \(Save [1-9]\)", name[marker:]):
        name, suffix = name[:marker], name[marker:]
    if not name:
        return header
    rest = line[len(RENAME_PREFIX):]
    if not rest.startswith(name + " to "):
        return header
    rest = rest[len(name) + 4:]
    tail = _DATE_TAIL.search(rest)
    if tail is None or len(rest) <= 14:
        return header
    new = rest[:-14]
    if not new or len(new) > 63 or any(not (0x20 <= ord(ch) <= 0x7E) for ch in new):
        return header
    return f"Village: {new}{suffix}"


def effective_header(text: str, header_line: int) -> str | None:
    """The village a log stands for: its header with every rename note applied.

    ``header_line`` is the 0-based line the exporter put the header on.
    """
    lines = text.splitlines()
    if len(lines) <= header_line or not lines[header_line].startswith("Village: "):
        return None
    header = lines[header_line]
    for line in lines[header_line + 1:]:
        header = apply_rename_note(header, line)
    return header


@dataclass(frozen=True)
class LogTarget:
    path: Path
    header_line: int    # where the header is: 0 for the record logs
    with_slot: bool = False   # a shared log: the note names the slot too


_RECORD_LOG = re.compile(
    r"^Virtual Villagers (\d) (?:Births and Conceptions|Parentage|Deaths|"
    r"Unaccounted Villagers) Log \d+\.txt$",
    re.IGNORECASE,
)
_POPULATION_PAGE = re.compile(r"^Village Population \d+\.txt$", re.IGNORECASE)
_HISTORY_FILE = re.compile(r"^Village History(?: (\d+))?\.txt$", re.IGNORECASE)


def _files(folder: Path) -> list[Path]:
    try:
        return sorted(
            (entry for entry in folder.iterdir() if entry.is_file()),
            key=lambda entry: entry.name.casefold(),
        )
    except OSError:
        return []


def _village_logs(game: GameSaves, folder: Path, slot: int) -> list[LogTarget]:
    """Every patcher log in ``folder`` that could name this slot's village.

    Only the exporters' own folders and file shapes; never the Backups folder.
    """
    targets: list[LogTarget] = []
    for root_name in (LOGS_FOLDER, LEGACY_LOGS_FOLDER):
        root = folder / root_name
        for sub in (
            "Births and Conceptions",
            "Tribe Parental Records",
            "Deaths",
            "Unaccounted Villagers",
        ):
            for path in _files(root / sub):
                match = _RECORD_LOG.match(path.name)
                if match and int(match.group(1)) == game.number:
                    targets.append(LogTarget(path, 0))
        for path in _files(root / "Tribe Population"):
            if _POPULATION_PAGE.match(path.name):
                targets.append(LogTarget(path, 1))
    statistics = folder / LOGS_FOLDER / "Village Statistics" / f"Village Statistics v2 - Save {slot}.txt"
    if statistics.is_file():
        targets.append(LogTarget(statistics, 2))
    # The Village History is shared by every village of the game, one dated
    # snapshot after another; its note goes in the newest file and names the
    # slot, and it is written whatever the last snapshot's village was.
    history = [
        path
        for path in _files(folder / LOGS_FOLDER / "Tribe History")
        if _HISTORY_FILE.match(path.name)
    ]
    if history:
        def number(path: Path) -> int:
            match = _HISTORY_FILE.match(path.name)
            return int(match.group(1)) if match and match.group(1) else 0
        targets.append(LogTarget(max(history, key=number), -1, with_slot=True))
    return targets


def _read_text(path: Path) -> str:
    return path.read_bytes().decode("latin-1")


@dataclass
class LogNote:
    path: Path
    original_size: int
    text: bytes


def plan_log_notes(
    game: GameSaves, folder: Path, slot: int, old: str, new: str, when: datetime
) -> list[LogNote]:
    """The line to append to each of this village's logs."""
    old_header = village_header(old, slot)
    note = rename_note(old, new, when)
    notes: list[LogNote] = []
    for target in _village_logs(game, folder, slot):
        try:
            data = target.path.read_bytes()
        except OSError as exc:
            raise RenameError(f"Could not read the log {target.path.name}: {exc}") from exc
        if target.with_slot:
            line = f"{note} (Save {slot})"
        else:
            text = data.decode("latin-1")
            if effective_header(text, target.header_line) != old_header:
                continue
            line = note
        prefix = b"" if not data or data.endswith(b"\n") else b"\r\n"
        notes.append(LogNote(target.path, len(data), prefix + line.encode("ascii") + b"\r\n\r\n"))
    return notes


# ---------------------------------------------------------------------------
# The rename
# ---------------------------------------------------------------------------


@dataclass
class FileChange:
    path: Path
    original: bytes
    updated: bytes


@dataclass
class RenameResult:
    folder: Path
    slot: int
    old_name: str
    new_name: str
    backup: vv_save_backup.BackupResult
    changed: list[Path] = field(default_factory=list)
    notes: list[Path] = field(default_factory=list)


def _refuse_if_running(folder: Path, processes: vv_save_backup.ProcessController) -> None:
    exe = vv_save_backup.game_exe_name(folder)
    try:
        running = processes.find(exe)
    except (OSError, vv_save_backup.BackupError) as exc:
        raise RenameError(
            f"Could not check whether {exe} is running, so nothing was changed ({exc})."
        ) from exc
    if running:
        raise GameRunning(
            f"{exe} is running. Close the game first (quit it normally from its "
            "menu): it saves when it quits, which would put the old name back. "
            "Nothing was changed."
        )


def plan_save_changes(
    game: GameSaves, folder: Path, slot: int, new_name: str
) -> tuple[str, list[FileChange]]:
    """The old name, and the new bytes of every save file that holds it."""
    save = game.save_path(folder, slot)
    try:
        data = save.read_bytes()
    except FileNotFoundError as exc:
        raise RenameError(f"Save {slot} has no tribe ({save.name} is missing).") from exc
    except OSError as exc:
        raise RenameError(f"Could not read {save.name}: {exc}") from exc
    old = save_name(game, data)
    layout = _save_layout(game, data)
    if old is None or layout is None:
        raise RenameError(f"{save.name} is not a {game.title} save this tool can read.")
    if old == new_name:
        raise RenameError(f"Save {slot} is already called {new_name}.")
    index_file = game.index_path(folder)
    try:
        index = index_file.read_bytes()
    except OSError as exc:
        raise RenameError(f"Could not read the slot list {index_file.name}: {exc}") from exc
    if index_name(game, index, slot) is None:
        raise RenameError(f"The slot list {index_file.name} is not one this tool can read.")
    changes = [
        FileChange(save, data, _with_name(data, layout[0] + game.name_offset, game.save_field, new_name))
    ]
    for generation in GENERATIONS:
        path = game.generation_path(folder, generation, slot)
        try:
            older = path.read_bytes()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise RenameError(f"Could not read {path.name}: {exc}") from exc
        older_layout = _save_layout(game, older)
        if older_layout is None or save_name(game, older) != old:
            continue        # another village, or not a save: left alone
        changes.append(
            FileChange(
                path,
                older,
                _with_name(older, older_layout[0] + game.name_offset, game.save_field, new_name),
            )
        )
    changes.append(
        FileChange(
            index_file,
            index,
            _with_name(index, game.index_offset(slot), game.index_stride, new_name),
        )
    )
    return old, changes


def _restore(changes: list[FileChange], notes: list[LogNote]) -> list[str]:
    """Put every changed file back; the reasons any could not be."""
    problems: list[str] = []
    for change in reversed(changes):
        try:
            if change.path.read_bytes() != change.original:
                _write_atomically(change.path, change.original)
        except (OSError, RenameError) as exc:
            problems.append(f"{change.path.name}: {exc}")
    for note in reversed(notes):
        try:
            if note.path.stat().st_size != note.original_size:
                with note.path.open("r+b") as handle:
                    handle.truncate(note.original_size)
        except OSError as exc:
            problems.append(f"{note.path.name}: {exc}")
    return problems


def rename_tribe(
    game: GameSaves,
    folder: Path,
    slot: int,
    new_name: str,
    processes: vv_save_backup.ProcessController | None = None,
    now: datetime | None = None,
) -> RenameResult:
    """Rename the tribe in ``slot`` of ``folder`` to ``new_name``.

    Refused (RenameError, nothing changed) when the name breaks the game's
    rule, the game is running, or the saves cannot be read. Otherwise the
    folder is backed up first, every file is replaced atomically and read
    back, and any failure restores every file already changed.
    """
    if slot not in SLOTS:
        raise RenameError(f"There is no save slot {slot}.")
    problem = name_problem(game, new_name)
    if problem is not None:
        raise RenameError(problem)
    controller = processes if processes is not None else vv_save_backup.WindowsProcesses()
    when = now or datetime.now()
    _refuse_if_running(folder, controller)
    old, changes = plan_save_changes(game, folder, slot, new_name)
    notes = plan_log_notes(game, folder, slot, old, new_name, when)
    try:
        backup = vv_save_backup.copy_save_folder(folder, when, suffix=BACKUP_LABEL)
    except vv_save_backup.BackupError as exc:
        raise RenameError(f"The backup before renaming failed, so nothing was changed. {exc}") from exc
    # The backup took a moment; the game may have been started meanwhile.
    _refuse_if_running(folder, controller)
    done: list[FileChange] = []
    appended: list[LogNote] = []
    try:
        for change in changes:
            if change.path.read_bytes() != change.original:
                raise RenameError(f"{change.path.name} changed while it was being renamed.")
            done.append(change)
            _write_atomically(change.path, change.updated)
        for note in notes:
            appended.append(note)
            with note.path.open("ab") as handle:
                if handle.tell() != note.original_size:
                    raise RenameError(f"{note.path.name} changed while it was being renamed.")
                handle.write(note.text)
                handle.flush()
                os.fsync(handle.fileno())
            with note.path.open("rb") as handle:
                handle.seek(note.original_size)
                if handle.read() != note.text:
                    raise RenameError(f"{note.path.name} did not read back as written.")
        # Read every file back through the same parsers the listing uses.
        index_file = game.index_path(folder)
        for change in changes:
            data = change.path.read_bytes()
            if change.path == index_file:
                holds = index_name(game, data, slot) == new_name
            else:
                holds = save_name(game, data) == new_name
            if not holds:
                raise RenameError(f"{change.path.name} does not hold the new name.")
    except (OSError, RenameError) as exc:
        problems = _restore(done, appended)
        if problems:
            raise RenameError(
                f"The rename failed ({exc}) and these files could not be put back: "
                f"{'; '.join(problems)}. Your backup is in {backup.backup_folder}."
            ) from exc
        raise RenameError(
            f"The rename failed ({exc}); every file was put back as it was. "
            f"A backup is in {backup.backup_folder}."
        ) from exc
    return RenameResult(
        folder,
        slot,
        old,
        new_name,
        backup,
        [change.path for change in changes],
        [note.path for note in notes],
    )


def rename_folders(title: str, documents: Path | None) -> list[Path]:
    """The save folders Rename Tribe offers for ``title``: the same
    "<title> - Modded..." folders Back Up and Restore Saves list (the patched
    games' saves), patcher-made ones first. The stock game's own folder is
    not offered."""
    return vv_save_backup.find_save_folders(title, documents)
