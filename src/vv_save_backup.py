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

Nothing here touches Tk, so the GUI runs it on a worker thread, and the tests
drive it with a fake Documents folder and a fake process controller.
"""
from __future__ import annotations

import ctypes
import hashlib
import sys
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


def _is_link(path: Path) -> bool:
    """A symbolic link or junction, which the copy never walks into."""
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    if is_junction is not None:
        return bool(is_junction())
    return False


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
            elif entry.is_file():
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

    @property
    def file_count(self) -> int:
        return len(self.files)

    @property
    def total_bytes(self) -> int:
        return sum(item.size for item in self.files)


def backup_folder_name(now: datetime) -> str:
    return f"{BACKUP_PREFIX}{now.strftime('%Y-%m-%d %H-%M-%S')}"


def _new_backup_folder(save_folder: Path, now: datetime) -> Path:
    """Create and return a backup folder that did not exist before.

    mkdir(exist_ok=False) is the claim: if the name is taken (two backups in
    one second, or one made by hand) the next free " (2)", " (3)" ... is used,
    so an existing backup is never written into.
    """
    backups = save_folder / BACKUPS_FOLDER
    backups.mkdir(exist_ok=True)
    base = backup_folder_name(now)
    for attempt in range(1, 1000):
        name = base if attempt == 1 else f"{base} ({attempt})"
        candidate = backups / name
        try:
            candidate.mkdir()
        except FileExistsError:
            continue
        return candidate
    raise BackupError(f"Too many backups named {base} in {backups}.")


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


def copy_save_folder(save_folder: Path, now: datetime | None = None) -> BackupResult:
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
    backup = _new_backup_folder(save_folder, now or datetime.now())
    result = BackupResult(save_folder, backup)
    try:
        for relative in relatives:
            copied = _copy_one(save_folder / relative, backup / relative)
            copied.relative = relative
            result.files.append(copied)
    except (OSError, BackupError) as exc:
        incomplete = backup.with_name(backup.name + " INCOMPLETE")
        try:
            backup.rename(incomplete)
            where = incomplete
        except OSError:
            where = backup
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


@contextmanager
def paused_game(
    exe_name: str, processes: ProcessController
) -> Iterator[int]:
    """Suspend every running process of ``exe_name``; always resume them.

    Yields how many were paused (0 when the game is not running). If any
    process cannot be paused, the ones already paused are resumed and
    PauseRefused is raised before the caller copies anything.
    """
    paused: list[object] = []
    try:
        for pid in processes.find(exe_name):
            paused.append(processes.suspend(pid, exe_name))
        yield len(paused)
    finally:
        errors: list[BaseException] = []
        for handle in reversed(paused):
            try:
                processes.resume(handle)
            except BaseException as exc:  # resume the rest before reporting
                errors.append(exc)
        if errors:
            raise errors[0]


def back_up_save_folder(
    save_folder: Path,
    processes: ProcessController | None = None,
    now: datetime | None = None,
) -> BackupResult:
    """Pause the game that uses ``save_folder`` (if running), copy, resume."""
    controller = processes if processes is not None else WindowsProcesses()
    with paused_game(game_exe_name(save_folder), controller) as count:
        result = copy_save_folder(save_folder, now)
        result.paused = count
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
