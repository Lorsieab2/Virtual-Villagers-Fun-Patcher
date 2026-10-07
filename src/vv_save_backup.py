"""Back Up Saves: pause a running game, then copy its save folder into itself.

The owner's request: "an easy tool to pause the player's saves and make a copy
of them in the save folder too", as a button in the patcher window that pauses
the game and then copies.

Where the saves are
    Every Virtual Villagers game saves under Documents\\LDW\\<its exe's name>.
    A patched game is "<title> - Modded.exe" (or "- Modded 256", "- Modded
    Playtest", "- Modded 256 Playtest"), so its saves are in
    Documents\\LDW\\<title> - Modded...\\. Documents is resolved through the
    Windows Known Folder API, because it may be redirected (to OneDrive, as on
    the owner's machine); a home-relative guess would name a folder the games
    never write to.

What is copied
    Everything in the save folder -- the game's .ldw saves, the patcher's
    "Virtual Villagers Fun Patcher Logs" and "Virtual Villagers Fun Patcher
    Data" folders with all their subfolders, and any other file the patcher
    keeps beside the saves -- except the "Backups" folder itself. The copy goes
    into a new "Backups\\Backup YYYY-MM-DD HH-MM-SS" folder inside that same
    save folder. An existing backup is never written into or replaced, and
    every copied file is read back and checked against the original's size and
    SHA-256.

Pausing
    If the game that uses the folder is running, every process of it is
    suspended for the copy and always resumed afterwards, even when the copy
    fails. If any of them cannot be suspended the backup is refused rather
    than taken while the game might be writing. The game is never closed.
    These games save only when the player quits normally, so a backup of a
    running game holds the village as of its last save.

Restore
    A backup is restored -- the whole save folder, or one save slot -- only
    while the game is closed, and only after the current saves have been
    backed up as "Backup <date> (before restore)". See restore_backup.

Nothing here touches Tk, so the GUI runs it on a worker thread, and the tests
drive it with a fake Documents folder and a fake process controller.
"""
from __future__ import annotations

import ctypes
import hashlib
import os
import re
import shutil
import stat
import sys
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterator, Protocol

# The folder the backups go into, inside each save folder. Every patcher
# feature that reads or deletes files in a save folder looks only at named
# files or at its own named subfolders, so nothing in here is ever read,
# migrated or deleted by them (tests/test_save_backup.py pins that).
BACKUPS_FOLDER = "Backups"
BACKUP_PREFIX = "Backup "

# The suffixes the patcher gives a built game, in the order they are listed.
# A save folder with one of these names was made by a patched game, so the
# chooser ticks it by default; other "<title> - Modded..." folders (a copy the
# player made, say) are listed but left for the player to tick.
PATCHER_SUFFIXES = (
    "Modded",
    "Modded 256",
    "Modded Playtest",
    "Modded 256 Playtest",
)

HASH_CHUNK = 1024 * 1024


class BackupError(Exception):
    """A backup that could not be made, with a reason a player can read."""


class PauseRefused(BackupError):
    """The game is running and could not be paused, so nothing was copied."""


# ---------------------------------------------------------------------------
# Documents and the save folders
# ---------------------------------------------------------------------------


def documents_folder() -> Path | None:
    """The Documents folder as Windows resolves it, or None if it cannot.

    SHGetKnownFolderPath(FOLDERID_Documents) follows folder redirection, so a
    Documents moved to OneDrive or a network share is found where the games
    actually save. There is deliberately no home-relative fallback: a guessed
    folder would only make the tool report "no saves found" for a player whose
    saves are elsewhere.
    """
    if sys.platform != "win32":
        return None
    try:
        from ctypes import wintypes

        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8),
            ]

        # FOLDERID_Documents {FDD39AD0-238F-46AF-ADB4-6C85480369C7}
        folder_id = GUID(
            0xFDD39AD0,
            0x238F,
            0x46AF,
            (ctypes.c_ubyte * 8)(0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7),
        )
        shell32 = ctypes.windll.shell32
        ole32 = ctypes.windll.ole32
        shell32.SHGetKnownFolderPath.argtypes = [
            ctypes.POINTER(GUID),
            wintypes.DWORD,
            wintypes.HANDLE,
            ctypes.POINTER(ctypes.c_wchar_p),
        ]
        shell32.SHGetKnownFolderPath.restype = ctypes.c_long
        ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
        ole32.CoTaskMemFree.restype = None
        result = ctypes.c_wchar_p()
        status = shell32.SHGetKnownFolderPath(
            ctypes.byref(folder_id), 0, None, ctypes.byref(result)
        )
        try:
            if status == 0 and result.value:
                return Path(result.value)
        finally:
            ole32.CoTaskMemFree(ctypes.cast(result, ctypes.c_void_p))
    except (OSError, AttributeError):
        pass
    return None


def is_patcher_save_folder(title: str, name: str) -> bool:
    """Whether ``name`` is the save folder of a game the patcher built."""
    return any(
        name.casefold() == f"{title} - {suffix}".casefold()
        for suffix in PATCHER_SUFFIXES
    )


def find_save_folders(title: str, documents: Path | None) -> list[Path]:
    """Every Documents\\LDW\\<title> - Modded... folder, patcher-made ones first.

    The stock game's own "<title>" folder is not listed: the tool backs up the
    patched games' saves. Any other folder whose name starts with
    "<title> - Modded" -- a copy the player made, a renamed test build -- is
    listed too, because a game run from such an exe saves there.
    """
    if documents is None:
        return []
    ldw = documents / "LDW"
    if not ldw.is_dir():
        return []
    prefix = f"{title} - Modded".casefold()
    found = [
        entry
        for entry in ldw.iterdir()
        if entry.name.casefold().startswith(prefix) and entry.is_dir()
    ]

    def order(path: Path) -> tuple[int, int, str]:
        names = [f"{title} - {suffix}".casefold() for suffix in PATCHER_SUFFIXES]
        key = path.name.casefold()
        if key in names:
            return (0, names.index(key), key)
        return (1, 0, key)

    return sorted(found, key=order)


def game_exe_name(save_folder: Path) -> str:
    """The exe that saves into ``save_folder``: the games name it after themselves."""
    return f"{save_folder.name}.exe"


# ---------------------------------------------------------------------------
# What is copied
# ---------------------------------------------------------------------------


_IO_REPARSE_TAG_MOUNT_POINT = 0xA0000003


def _is_link(path: Path) -> bool:
    """A symbolic link or junction, which the copy never follows.

    A junction is recognised by its reparse tag, which every supported Python
    reports on Windows (Path.is_junction only exists from Python 3.12). Other
    reparse points -- OneDrive's cloud files and folders -- are ordinary
    content and are copied.
    """
    if path.is_symlink():
        return True
    try:
        tag = getattr(path.lstat(), "st_reparse_tag", 0)
    except OSError:
        return False
    return tag == _IO_REPARSE_TAG_MOUNT_POINT


def files_to_back_up(save_folder: Path) -> list[Path]:
    """Every file under ``save_folder`` except those in its Backups folder.

    Paths are returned relative to the save folder, sorted. A linked folder
    (junction or symbolic link) inside the save folder is not entered, so a
    link can never pull an unrelated tree -- or the save folder itself -- into
    the copy.
    """
    files: list[Path] = []

    def walk(folder: Path, relative: Path) -> None:
        for entry in sorted(folder.iterdir(), key=lambda item: item.name.casefold()):
            if relative == Path() and entry.name.casefold() == BACKUPS_FOLDER.casefold():
                continue
            if entry.is_dir():
                if not _is_link(entry):
                    walk(entry, relative / entry.name)
            elif entry.is_file() and not _is_link(entry):
                files.append(relative / entry.name)

    walk(save_folder, Path())
    return files


# ---------------------------------------------------------------------------
# The copy
# ---------------------------------------------------------------------------


@dataclass
class CopiedFile:
    relative: Path
    size: int
    sha256: str


@dataclass
class BackupResult:
    save_folder: Path
    backup_folder: Path
    files: list[CopiedFile] = field(default_factory=list)
    paused: int = 0          # how many game processes were paused for the copy
    resume_problems: list[str] = field(default_factory=list)

    @property
    def file_count(self) -> int:
        return len(self.files)

    @property
    def total_bytes(self) -> int:
        return sum(item.size for item in self.files)


def backup_folder_name(now: datetime) -> str:
    return f"{BACKUP_PREFIX}{now.strftime('%Y-%m-%d %H-%M-%S')}"


IN_PROGRESS = " (in progress)"


def _backup_names(now: datetime, suffix: str) -> Iterator[str]:
    base = backup_folder_name(now)
    for attempt in range(1, 1000):
        name = base if attempt == 1 else f"{base} ({attempt})"
        yield f"{name} {suffix}" if suffix else name


def _new_backup_folder(save_folder: Path, now: datetime, suffix: str = "") -> Path:
    """Create and return a new, empty "... (in progress)" folder.

    The backup is made under this name, which list_backups never offers, and
    is renamed to its final name only once every file has been verified -- so
    a copy that fails or is interrupted can never look like a usable backup.
    mkdir(exist_ok=False) is the claim, and a name whose final folder already
    exists is skipped, so an existing backup is never written into.
    """
    backups = save_folder / BACKUPS_FOLDER
    backups.mkdir(exist_ok=True)
    for name in _backup_names(now, suffix):
        if (backups / name).exists():
            continue
        candidate = backups / (name + IN_PROGRESS)
        try:
            candidate.mkdir()
        except FileExistsError:
            continue
        return candidate
    raise BackupError(f"Too many backups named {backup_folder_name(now)} in {backups}.")


def _finish_backup(staging: Path, now: datetime, suffix: str) -> Path:
    """Give a verified backup its final name: the first one still free."""
    for name in _backup_names(now, suffix):
        final = staging.with_name(name)
        if final.exists():
            continue
        for attempt in range(DELETE_ATTEMPTS):
            try:
                staging.rename(final)
                return final
            except FileExistsError:
                break
            except PermissionError:
                # A sync or indexing program (OneDrive) can hold a folder it
                # has just seen created for a moment.
                if attempt == DELETE_ATTEMPTS - 1:
                    raise
                time.sleep(DELETE_RETRY_SECONDS)
    raise BackupError(f"No free name for the backup in {staging.parent}.")


def _set_aside(staging: Path, label: str) -> Path:
    """Rename a failed backup "... INCOMPLETE", "... INCOMPLETE (2)" ...

    If no rename succeeds it stays "... (in progress)", which is not offered
    as a backup either.
    """
    base = staging.name.removesuffix(IN_PROGRESS) + label
    for attempt in range(1, 100):
        target = staging.with_name(base if attempt == 1 else f"{base} ({attempt})")
        if target.exists():
            continue
        try:
            staging.rename(target)
        except OSError:
            continue
        return target
    return staging


def _hash_file(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(HASH_CHUNK)
            if not chunk:
                break
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def _copy_one(source: Path, destination: Path) -> CopiedFile:
    """Copy one file, never over an existing one, and verify it by size and hash."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    size = 0
    with source.open("rb") as reader, destination.open("xb") as writer:
        while True:
            chunk = reader.read(HASH_CHUNK)
            if not chunk:
                break
            size += len(chunk)
            digest.update(chunk)
            writer.write(chunk)
    expected = digest.hexdigest()
    copied_size, copied_hash = _hash_file(destination)
    if copied_size != size or copied_hash != expected:
        raise BackupError(
            f"The copy of {source.name} does not match the original "
            f"({copied_size} of {size} bytes)."
        )
    # The original must still be what was read: a file that changed while it
    # was being copied would leave a backup of neither version.
    source_size, source_hash = _hash_file(source)
    if source_size != size or source_hash != expected:
        raise BackupError(f"{source.name} changed while it was being copied.")
    return CopiedFile(Path(), size, expected)


def copy_save_folder(
    save_folder: Path, now: datetime | None = None, suffix: str = ""
) -> BackupResult:
    """Copy the save folder into a new Backups\\Backup <date> folder inside it.

    On any failure the partial backup is renamed "... INCOMPLETE" (never
    deleted, and never left looking like a good backup) and BackupError is
    raised.
    """
    if not save_folder.is_dir():
        raise BackupError(f"The save folder does not exist: {save_folder}")
    relatives = files_to_back_up(save_folder)
    if not relatives:
        raise BackupError(f"There is nothing to back up in {save_folder}.")
    when = now or datetime.now()
    staging = _new_backup_folder(save_folder, when, suffix)
    result = BackupResult(save_folder, staging)
    try:
        for relative in relatives:
            copied = _copy_one(save_folder / relative, staging / relative)
            copied.relative = relative
            result.files.append(copied)
        result.backup_folder = _finish_backup(staging, when, suffix)
    except (OSError, BackupError) as exc:
        where = _set_aside(staging, INCOMPLETE)
        reason = exc if isinstance(exc, BackupError) else f"{type(exc).__name__}: {exc}"
        raise BackupError(
            f"The backup could not be completed ({reason}). The partial copy "
            f"was kept as {where} and is NOT a usable backup."
        ) from exc
    return result


# ---------------------------------------------------------------------------
# Pausing the game
# ---------------------------------------------------------------------------


class ProcessController(Protocol):
    def find(self, exe_name: str) -> list[int]: ...
    def suspend(self, pid: int, exe_name: str) -> object: ...
    def resume(self, handle: object) -> None: ...


class WindowsProcesses:
    """Find, suspend and resume game processes with the Windows API."""

    PROCESS_SUSPEND_RESUME = 0x0800
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    TH32CS_SNAPPROCESS = 0x00000002
    ERROR_NO_MORE_FILES = 18

    def __init__(self) -> None:
        from ctypes import wintypes

        self._wintypes = wintypes
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._ntdll = ctypes.WinDLL("ntdll")
        k = self._kernel32
        k.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        k.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        k.OpenProcess.restype = wintypes.HANDLE
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        k.CloseHandle.restype = wintypes.BOOL
        k.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
        ]
        k.QueryFullProcessImageNameW.restype = wintypes.BOOL
        for name in ("NtSuspendProcess", "NtResumeProcess"):
            function = getattr(self._ntdll, name)
            function.argtypes = [wintypes.HANDLE]
            function.restype = ctypes.c_long

        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD),
                ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t),
                ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", wintypes.LONG),
                ("dwFlags", wintypes.DWORD),
                ("szExeFile", wintypes.WCHAR * 260),
            ]

        self._entry_type = PROCESSENTRY32W
        k.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
        k.Process32FirstW.restype = wintypes.BOOL
        k.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
        k.Process32NextW.restype = wintypes.BOOL

    def find(self, exe_name: str) -> list[int]:
        k = self._kernel32
        snapshot = k.CreateToolhelp32Snapshot(self.TH32CS_SNAPPROCESS, 0)
        if not snapshot or snapshot == self._wintypes.HANDLE(-1).value:
            raise BackupError(
                "Could not list the running programs to check whether the game is "
                f"running (error {ctypes.get_last_error()})."
            )
        pids: list[int] = []
        try:
            entry = self._entry_type()
            entry.dwSize = ctypes.sizeof(entry)
            more = k.Process32FirstW(snapshot, ctypes.byref(entry))
            while more:
                if entry.szExeFile.casefold() == exe_name.casefold():
                    pids.append(int(entry.th32ProcessID))
                more = k.Process32NextW(snapshot, ctypes.byref(entry))
            # FALSE means either "no more processes" or a failure; only the
            # first is a complete list.
            error = ctypes.get_last_error()
            if error != self.ERROR_NO_MORE_FILES:
                raise BackupError(
                    "Could not read the whole list of running programs to check "
                    f"whether the game is running (error {error})."
                )
        finally:
            k.CloseHandle(snapshot)
        return pids

    def suspend(self, pid: int, exe_name: str) -> object:
        k = self._kernel32
        handle = k.OpenProcess(
            self.PROCESS_SUSPEND_RESUME | self.PROCESS_QUERY_LIMITED_INFORMATION,
            False,
            pid,
        )
        if not handle:
            error = ctypes.get_last_error()
            reason = "access was denied" if error == 5 else f"Windows error {error}"
            raise PauseRefused(
                f"{exe_name} (process {pid}) is running but could not be paused: "
                f"{reason}."
            )
        try:
            # The process list was taken a moment ago; make sure this id still
            # belongs to the game before pausing it.
            buffer = ctypes.create_unicode_buffer(32768)
            length = self._wintypes.DWORD(len(buffer))
            if not k.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(length)):
                raise PauseRefused(
                    f"{exe_name} (process {pid}) could not be checked before pausing "
                    f"(Windows error {ctypes.get_last_error()})."
                )
            if Path(buffer.value).name.casefold() != exe_name.casefold():
                raise PauseRefused(
                    f"Process {pid} is no longer {exe_name}; try the backup again."
                )
            status = self._ntdll.NtSuspendProcess(handle)
            if status != 0:
                raise PauseRefused(
                    f"{exe_name} (process {pid}) is running but could not be paused "
                    f"(status 0x{status & 0xFFFFFFFF:08X})."
                )
        except BaseException:
            k.CloseHandle(handle)
            raise
        return handle

    def resume(self, handle: object) -> None:
        try:
            status = self._ntdll.NtResumeProcess(handle)
            if status != 0:
                raise BackupError(
                    f"The game could not be resumed (status 0x{status & 0xFFFFFFFF:08X}). "
                    "Close it from Task Manager if it stays frozen."
                )
        finally:
            self._kernel32.CloseHandle(handle)


@dataclass
class Pause:
    count: int = 0                                   # processes paused
    problems: list[str] = field(default_factory=list)  # resumes that failed


@contextmanager
def paused_game(
    exe_name: str, processes: ProcessController
) -> Iterator[Pause]:
    """Suspend every running process of ``exe_name``; always resume them.

    If any process cannot be paused, the ones already paused are resumed and
    PauseRefused is raised before the caller copies anything. Every paused
    process is resumed even if another's resume fails; a failed resume is
    recorded in ``Pause.problems`` (or noted on the error already on its way
    out), so a backup that succeeded is still reported as made.
    """
    pause = Pause()
    paused: list[object] = []
    failure: BaseException | None = None
    try:
        for pid in processes.find(exe_name):
            paused.append(processes.suspend(pid, exe_name))
        pause.count = len(paused)
        yield pause
    except BaseException as exc:
        failure = exc
        raise
    finally:
        errors: list[str] = []
        for handle in reversed(paused):
            try:
                processes.resume(handle)
            except Exception as exc:  # resume the rest before reporting
                errors.append(str(exc))
        if errors:
            if failure is not None:
                failure.add_note("The game could not be resumed: " + "; ".join(errors))
            else:
                pause.problems.extend(errors)


def back_up_save_folder(
    save_folder: Path,
    processes: ProcessController | None = None,
    now: datetime | None = None,
) -> BackupResult:
    """Pause the game that uses ``save_folder`` (if running), copy, resume."""
    controller = processes if processes is not None else WindowsProcesses()
    with paused_game(game_exe_name(save_folder), controller) as pause:
        result = copy_save_folder(save_folder, now)
    result.paused = pause.count
    result.resume_problems = list(pause.problems)
    return result


def running_game_count(save_folder: Path, processes: ProcessController | None = None) -> int:
    """How many processes of the game that saves here are running (0 if none or unknown)."""
    try:
        controller = processes if processes is not None else WindowsProcesses()
        return len(controller.find(game_exe_name(save_folder)))
    except (OSError, BackupError, AttributeError):
        return 0


def describe_size(size: int) -> str:
    if size < 1024:
        return f"{size} bytes"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


# ---------------------------------------------------------------------------
# Restore
# ---------------------------------------------------------------------------
#
# The owner: "Is there a backup and restore feature for vv saves? The player
# should be able to choose from a list." A backup is restored only while the
# game is closed (a running game writes its village over the restored save
# when it quits), and only after the current state has itself been backed up
# as "Backup <date> (before restore)", so every restore can be undone. A
# backup is never modified by a restore; only Delete Backup removes one.

BEFORE_RESTORE = "(before restore)"
# Rename Tribe (src/vv_tribe_rename.py) backs the folder up first under this
# label; such a backup is listed and restored like any other.
BEFORE_RENAME = "(before rename)"
# Repair Saves & Logs (src/vv_log_tools.py) backs the folder up first under this label.
BEFORE_REARM = "(before repair re-arm)"
INCOMPLETE = " INCOMPLETE"
_BACKUP_NAME = re.compile(r"^Backup (\d{4}-\d{2}-\d{2} \d{2}-\d{2}-\d{2})(?: \((\d+)\))?(?: (\(before (?:restore|rename|repair re-arm)\)))?$")
_TEMP_GLOB = "*.vvfp-restore-*.tmp"

# The game's save file: a small file header, then the save buffer (measured
# per game; see native/save_reset_export/save_reset_export.c and
# native/shared/village_identity.c, which read the same names the same way).
_SAVE_HEADER = {1: 12, 2: 12, 3: 12, 4: 24, 5: 24}
_SAVE_LENGTH_AT = {1: 8, 2: 8, 3: 8, 4: 16, 5: 16}
_SAVE_BUFFERS = {
    1: (0x0ABDC,),
    2: (0x30370,),
    3: (0x12F1C, 0x1A4B4),   # stock, 256 Villagers (Experimental)
    4: (0x1710C, 0x1DCB4),
    5: (0x17D78, 0x1F168),
}
_NAME_OFFSET = {1: 0x8, 2: 0x8, 3: 0x12ECC, 4: 0x170B8, 5: 0x17D14}
_NAME_MAX = 64

# Patcher files that name their slot as "<stem>_<slot>.dat" (the names used
# before the data files moved into "Virtual Villagers Fun Patcher Data").
_LEGACY_SLOT_FILE = re.compile(
    r"^(?:vv1_masks|vv1_doublers|vv1_parents|vv2_masks|vvfp_masks)_([1-5])\.dat$", re.I
)
# Every patcher data file and per-save log names its slot as
# "<stem> - Save <slot>.dat|.txt", with the companions' ".tmp" and
# ".unreadable-..." variants. Only files inside the patcher's own folders (and
# the one statistics log that used to sit beside the saves) are attributed.
_SAVE_N = re.compile(r" - Save ([1-5])\.(?:dat|txt)(?:\.tmp|\.unreadable-[^\\/]*)?$", re.I)
_PATCHER_FOLDERS = (
    "virtual villagers fun patcher logs",
    "virtual villagers fun patcher data",
    "vvfp logs",
)
_LOG_FOLDERS = ("virtual villagers fun patcher logs", "vvfp logs")
# Village-headed logs (births, deaths, unaccounted, population pages) are
# numbered by roll-over, not by slot; their header names the slot instead.
_HEADER_SAVE_N = re.compile(r"^Village: .*\(Save ([1-5])\)\s*$")
# The game engine's own diagnostic log, which is not part of any save.
ENGINE_LOG = "ldwLog.txt"


class RestoreRefused(BackupError):
    """A restore that was not started, with the reason; nothing was changed."""


@dataclass
class BackupInfo:
    path: Path
    when: datetime
    before_restore: bool
    file_count: int
    size: int
    villages: dict[int, str]     # slot -> village name ("" when unreadable)
    before_rename: bool = False
    before_rearm: bool = False

    @property
    def label(self) -> str:
        text = self.when.strftime("%Y-%m-%d %H:%M:%S")
        if self.before_restore:
            text += " " + BEFORE_RESTORE
        if self.before_rename:
            text += " " + BEFORE_RENAME
        if self.before_rearm:
            text += " " + BEFORE_REARM
        return text


def game_number(save_folder: Path) -> int | None:
    """1-5 for a save folder named after one of the five games, else None."""
    titles = {
        "Virtual Villagers - A New Home": 1,
        "Virtual Villagers - The Lost Children": 2,
        "Virtual Villagers - The Secret City": 3,
        "Virtual Villagers - The Tree of Life": 4,
        "Virtual Villagers - New Believers": 5,
    }
    name = save_folder.name.casefold()
    for title, number in titles.items():
        if name.startswith(f"{title} - Modded".casefold()):
            return number
    return None


def _save_number(name: str) -> int | None:
    """The number in "<base><number>.ldw", or None for anything else."""
    match = re.fullmatch(r"(.*\D)(\d+)\.ldw", name, re.I)
    return int(match.group(2)) if match else None


def read_village_name(game: int, path: Path) -> str | None:
    """The village name in a slot's save file, or None if it is not a valid save.

    Read-only. The file must open with "ldwg", hold the game's buffer length
    in its length field and be exactly header + buffer long, as the patcher's
    companions require before they trust a name.
    """
    try:
        data = path.read_bytes()
    except OSError:
        return None
    header = _SAVE_HEADER[game]
    if len(data) < header or data[:4] != b"ldwg":
        return None
    length = int.from_bytes(data[_SAVE_LENGTH_AT[game]:_SAVE_LENGTH_AT[game] + 4], "little")
    if length not in _SAVE_BUFFERS[game] or len(data) != header + length:
        return None
    raw = data[header + _NAME_OFFSET[game]: header + _NAME_OFFSET[game] + _NAME_MAX]
    name = raw.split(b"\0", 1)[0]
    if any(byte < 0x20 or byte > 0x7E for byte in name):
        return ""
    return name.decode("ascii")


def _parse_backup_name(name: str) -> tuple[datetime, int, str] | None:
    """(when, sequence, label) -- the label "", BEFORE_RESTORE, BEFORE_RENAME or BEFORE_REARM."""
    match = _BACKUP_NAME.match(name)
    if not match:
        return None
    try:
        when = datetime.strptime(match.group(1), "%Y-%m-%d %H-%M-%S")
    except ValueError:
        return None
    return when, int(match.group(2) or 1), match.group(3) or ""


def slot_villages(game: int, folder: Path) -> dict[int, str]:
    """Slot -> village name for every slot whose own save is in ``folder``."""
    villages: dict[int, str] = {}
    try:
        entries = list(folder.iterdir())
    except OSError:
        return villages
    for entry in entries:
        number = _save_number(entry.name)
        if number is None or not 1 <= number <= 5 or not entry.is_file():
            continue
        name = read_village_name(game, entry)
        if name is not None:
            villages[number] = name
    return dict(sorted(villages.items()))


def list_backups(save_folder: Path) -> list[BackupInfo]:
    """The usable backups in ``save_folder``\\Backups, newest first.

    Only folders this tool names ("Backup <date>", "Backup <date> (2)",
    "Backup <date> (before restore)") are listed; an "... INCOMPLETE" copy
    is not a usable backup and is never offered.
    """
    backups = save_folder / BACKUPS_FOLDER
    game = game_number(save_folder)
    found: list[tuple[datetime, int, BackupInfo]] = []
    if not backups.is_dir():
        return []
    for entry in backups.iterdir():
        parsed = _parse_backup_name(entry.name)
        if parsed is None or not entry.is_dir() or _is_link(entry):
            continue
        when, sequence, label = parsed
        files = files_to_back_up(entry)
        size = sum((entry / relative).stat().st_size for relative in files)
        villages = slot_villages(game, entry) if game else {}
        found.append((
            when,
            sequence,
            BackupInfo(
                entry, when, label == BEFORE_RESTORE, len(files), size, villages,
                before_rename=label == BEFORE_RENAME,
                before_rearm=label == BEFORE_REARM,
            ),
        ))
    found.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [info for _when, _sequence, info in found]


def file_slot(relative: Path, folder: Path) -> int | str:
    """Which save slot a file in a save folder (or backup) belongs to.

    Returns 1-5, "engine log" for the game engine's own diagnostic log,
    "meta" for the game's shared slot-0 save, or "unknown". ``folder`` is
    where the file is, so a village-headed log's header can be read.
    """
    name = relative.name
    if len(relative.parts) == 1:
        number = _save_number(name)
        if number is not None:
            if number == 0:
                return "meta"
            if 1 <= number <= 5 or 21 <= number <= 25 or 41 <= number <= 45:
                return (number - 1) % 20 + 1    # N, N+20, N+40: one village's generations
            return "unknown"
        if name.casefold() == ENGINE_LOG.casefold():
            return "engine log"
    top = relative.parts[0].casefold()
    if len(relative.parts) == 1:
        match = _LEGACY_SLOT_FILE.match(name)
        if match:
            return int(match.group(1))
        match = re.fullmatch(r"Village Statistics - Save ([1-5])\.txt", name, re.I)
        return int(match.group(1)) if match else "unknown"
    if top not in _PATCHER_FOLDERS:
        return "unknown"
    match = _SAVE_N.search(name)
    if match:
        return int(match.group(1))
    if top in _LOG_FOLDERS and name.lower().endswith(".txt"):
        try:
            with (folder / relative).open("r", encoding="utf-8", errors="replace") as handle:
                head = [handle.readline() for _ in range(3)]
        except OSError:
            return "unknown"
        for line in head:
            match = _HEADER_SAVE_N.match(line.strip())
            if match:
                return int(match.group(1))
    return "unknown"


@dataclass
class RestorePlan:
    save_folder: Path
    backup: Path
    slot: int | None                      # None: the whole save folder
    replace: list[Path] = field(default_factory=list)   # in both; backup's copy wins
    add: list[Path] = field(default_factory=list)       # only in the backup
    remove: list[Path] = field(default_factory=list)    # only in the save folder now
    unchanged: list[Path] = field(default_factory=list)

    @property
    def changes(self) -> int:
        return len(self.replace) + len(self.add) + len(self.remove)


def _same_file(a: Path, b: Path) -> bool:
    try:
        return _hash_file(a) == _hash_file(b)
    except OSError:
        return False


def plan_restore(save_folder: Path, backup: Path, slot: int | None = None) -> RestorePlan:
    """Work out exactly which files a restore replaces, adds and removes.

    Whole folder: the save folder becomes the backup -- every file in it is
    restored and every other file (outside Backups) is removed.

    One slot: only files that belong to that slot on both sides are touched.
    It is refused (RestoreRefused, nothing changed) when a file that cannot
    be attributed to a slot -- the game's shared slot-0 save, or a patcher
    file with no slot in its name or header -- differs between the backup and
    the save folder, because restoring the slot without it, or with it, would
    each leave the other slots or this one inconsistent; and when a file the
    backup would put back is now another slot's (a log page number reused by
    another village).
    """
    _require_backup_of(save_folder, backup)
    in_backup = set(files_to_back_up(backup))
    in_folder = set(files_to_back_up(save_folder))
    plan = RestorePlan(save_folder, backup, slot)
    for relative in sorted(in_backup | in_folder, key=lambda p: str(p).casefold()):
        here = relative in in_folder
        there = relative in in_backup
        if slot is not None:
            owner_backup = file_slot(relative, backup) if there else None
            owner_folder = file_slot(relative, save_folder) if here else None
            owners = {owner for owner in (owner_backup, owner_folder) if owner is not None}
            if owners == {"engine log"}:
                continue
            if slot not in owners:
                if owners & {"meta", "unknown"} and not (
                    here and there and _same_file(save_folder / relative, backup / relative)
                ):
                    what = (
                        "the game's shared save (slot 0), which records every slot"
                        if "meta" in owners
                        else "a file that does not say which save it belongs to"
                    )
                    raise RestoreRefused(
                        f"Only the whole save folder can be restored from this backup: "
                        f"{relative} is {what}, and it is different in the backup."
                    )
                continue
            if len(owners) > 1:
                raise RestoreRefused(
                    f"Only the whole save folder can be restored from this backup: "
                    f"{relative} belongs to Save {slot} in one copy and not in the other."
                )
        if here and there:
            if _same_file(save_folder / relative, backup / relative):
                plan.unchanged.append(relative)
            else:
                plan.replace.append(relative)
        elif there:
            plan.add.append(relative)
        else:
            plan.remove.append(relative)
    if slot is not None and not any(
        file_slot(p, backup) == slot for p in in_backup
    ):
        raise RestoreRefused(f"This backup holds nothing for Save {slot}.")
    return plan


def _require_backup_of(save_folder: Path, backup: Path) -> None:
    """A backup must be a folder this tool made, directly inside Backups."""
    backups = (save_folder / BACKUPS_FOLDER).resolve()
    if (
        backup.resolve().parent != backups
        or _parse_backup_name(backup.name) is None
        or not backup.is_dir()
        or _is_link(backup)
    ):
        raise RestoreRefused(f"{backup} is not one of this save folder's backups.")


def _place(source: Path, target: Path) -> None:
    """Replace ``target`` with a verified copy of ``source``, atomically.

    The copy is written beside the target, checked against the source by
    size and SHA-256, and only then moved over the target with os.replace,
    so the target is at every moment either its old file or the new one.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    expected = _hash_file(source)
    while True:
        temp = target.with_name(f"{target.name}.vvfp-restore-{uuid.uuid4().hex[:12]}.tmp")
        try:
            writer = temp.open("xb")     # a name nothing else holds
        except FileExistsError:
            continue
        break
    try:
        with source.open("rb") as reader, writer:
            while True:
                chunk = reader.read(HASH_CHUNK)
                if not chunk:
                    break
                writer.write(chunk)
        if _hash_file(temp) != expected:
            raise BackupError(f"The restored copy of {target.name} did not match the backup.")
        os.replace(temp, target)
    finally:
        if temp.exists():
            temp.unlink()
    if _hash_file(target) != expected:
        raise BackupError(f"{target.name} did not match the backup after it was restored.")


@dataclass
class RestoreResult:
    plan: RestorePlan
    before_restore: BackupResult | None


def _game_running(save_folder: Path, processes: ProcessController) -> int:
    return len(processes.find(game_exe_name(save_folder)))


def restore_backup(
    save_folder: Path,
    backup: Path,
    slot: int | None = None,
    processes: ProcessController | None = None,
    now: datetime | None = None,
) -> RestoreResult:
    """Restore ``backup`` (all of it, or one slot) into ``save_folder``.

    Refused while the game is running. First backs the current state up as
    "Backup <date> (before restore)", then applies the plan file by file. On
    any failure every file already changed is put back from that before-
    restore backup, and the error says whether that succeeded.
    """
    controller = processes if processes is not None else WindowsProcesses()
    if _game_running(save_folder, controller):
        raise RestoreRefused(
            f"{game_exe_name(save_folder)} is running. Quit the game from its own "
            "menu first: a running game writes its village over the restored save "
            "when it quits. Nothing was changed."
        )
    plan = plan_restore(save_folder, backup, slot)
    if plan.changes == 0:
        return RestoreResult(plan, None)
    before = None
    if files_to_back_up(save_folder):
        before = copy_save_folder(save_folder, now, suffix=BEFORE_RESTORE)
    # The game could have been started while the safety backup was made.
    if _game_running(save_folder, controller):
        raise RestoreRefused(
            f"{game_exe_name(save_folder)} was started during the restore, so it was "
            f"stopped before anything was changed. Your current saves are also in "
            f"{before.backup_folder if before else 'the save folder'}."
        )
    done: list[Path] = []
    started = (
        f"{game_exe_name(save_folder)} was started during the restore. Quit it from "
        "its own menu and restore again."
    )
    try:
        for relative in plan.replace + plan.add:
            if _game_running(save_folder, controller):
                raise BackupError(started)
            done.append(relative)
            _place(backup / relative, save_folder / relative)
        for relative in plan.remove:
            if _game_running(save_folder, controller):
                raise BackupError(started)
            done.append(relative)
            (save_folder / relative).unlink()
    except (OSError, BackupError) as exc:
        problems = _roll_back(save_folder, before, done)
        if problems:
            raise BackupError(
                f"The restore failed ({exc}) and some files could not be put back: "
                f"{', '.join(problems)}. Your saves as they were before the restore "
                f"are in {before.backup_folder if before else '(no files)'}."
            ) from exc
        raise BackupError(
            f"The restore failed ({exc}). Every file was put back as it was; "
            "nothing changed."
        ) from exc
    return RestoreResult(plan, before)


def _roll_back(save_folder: Path, before: BackupResult | None, done: list[Path]) -> list[str]:
    problems: list[str] = []
    for relative in reversed(done):
        target = save_folder / relative
        original = before.backup_folder / relative if before else None
        try:
            if original is not None and original.is_file():
                _place(original, target)
            elif target.exists():
                target.unlink()
        except (OSError, BackupError):
            problems.append(str(relative))
    return problems


DELETING = " (deleting)"
DELETE_ATTEMPTS = 5
DELETE_RETRY_SECONDS = 0.5


def _clear_read_only(path: str) -> None:
    """Clear the read-only attribute, which OneDrive and Explorer set on folders."""
    try:
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    except OSError:
        pass


def delete_backup(save_folder: Path, backup: Path) -> None:
    """Delete one backup folder, which must be one of this save folder's backups.

    The folder is first renamed "... (deleting)", which takes it off the list
    in one step, so a delete that is interrupted part-way never leaves a
    half-emptied folder that still looks like a usable backup. Read-only
    files and folders (OneDrive marks folders read-only) are made writable as
    they are removed, and a file briefly held by a sync or indexing program is
    retried. If the rename itself is refused nothing has been deleted.
    """
    _require_backup_of(save_folder, backup)
    doomed = backup.with_name(backup.name + DELETING)
    try:
        backup.rename(doomed)
    except OSError as exc:
        raise BackupError(
            f"The backup could not be deleted ({exc}); nothing was deleted. "
            "If another program has it open, close that and try again."
        ) from exc

    def retry_writable(function, path, _error):
        _clear_read_only(path)
        parent = os.path.dirname(path)
        if parent:
            _clear_read_only(parent)
        function(path)

    last: OSError | None = None
    for attempt in range(DELETE_ATTEMPTS):
        try:
            shutil.rmtree(doomed, onexc=retry_writable)
            return
        except FileNotFoundError:
            return
        except OSError as exc:
            last = exc
            time.sleep(DELETE_RETRY_SECONDS)
    raise BackupError(
        f"The backup was taken off the list but its folder could not be removed "
        f"completely ({last}). You can delete {doomed} yourself; it is no longer "
        "a usable backup."
    )
