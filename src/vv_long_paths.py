"""Paths of 260 characters or more in the save folders (the owner, 2026-11-20: "no path-too-long errors").

Windows refuses a path of 260 characters or more (MAX_PATH) unless the machine has long paths turned on
(LongPathsEnabled), which most players' machines do not.  A save folder can hold such paths all the same:
the copies older builds kept in "Copies Made Before Repairs" under their full names ("...\\Virtual Villagers
1 Parentage Records - Save 1.dat.before-parents-restore"), and every file of a Back Up Saves backup, one
"Backups\\Backup <date> (...)" folder deeper than the file it copies.  Nothing here renames or deletes them.

Every patcher read, write, listing or delete that can meet such a path goes through `extended`: Windows'
extended-length form ("\\\\?\\C:\\...", "\\\\?\\UNC\\server\\share\\..."), which every file API accepts at any
length whatever the setting.  `walk` lists a folder tree that way and hands back ordinary paths (shown to
the player, compared with other paths); `plain` takes the prefix off again.  Off Windows both are the path
itself."""
from __future__ import annotations

import os
import shutil
import stat as _stat
from pathlib import Path
from typing import Callable, Iterator

from patcher_files import long_path as extended   # `path` in the extended-length form   # noqa: F401
from patcher_files import plain_path as plain     # ...and without its prefix                # noqa: F401

LIMIT = 259                       # the longest path Windows takes without long paths turned on


def too_long(path: os.PathLike | str) -> bool:
    """Would Windows refuse `path` (its absolute form) without long paths turned on?"""
    return len(os.path.abspath(os.fspath(plain(path)))) > LIMIT


def exists(path: os.PathLike | str) -> bool:
    return extended(path).exists()


def is_file(path: os.PathLike | str) -> bool:
    return extended(path).is_file()


def is_dir(path: os.PathLike | str) -> bool:
    return extended(path).is_dir()


def stat(path: os.PathLike | str) -> os.stat_result:
    return os.stat(extended(path))


def lstat(path: os.PathLike | str) -> os.stat_result:
    return os.lstat(extended(path))


def read_bytes(path: os.PathLike | str) -> bytes:
    return extended(path).read_bytes()


def mtime(path: os.PathLike | str) -> float:
    return stat(path).st_mtime


def is_link(entry_path: os.PathLike | str) -> bool:
    """A symbolic link or junction (never followed)."""
    try:
        st = lstat(entry_path)
    except OSError:
        return False
    if _stat.S_ISLNK(st.st_mode):
        return True
    return getattr(st, "st_reparse_tag", 0) == 0xA0000003      # IO_REPARSE_TAG_MOUNT_POINT


def walk(root: os.PathLike | str, *, skip: Callable[[Path], bool] | None = None,
         errors: list[str] | None = None, link: Callable[[Path], bool] | None = None) -> Iterator[Path]:
    """Every file under `root`, at any depth and length, as an ordinary path under `root` as given;
    sorted by name within each folder.  A link or junction -- or what `link(path)` also calls one -- is
    never entered or listed; a folder `skip(path)` says is passed by.  A folder that cannot be listed is
    named in `errors` (when given) and passed by -- or, with no `errors` list, raises its OSError: never
    left out unsaid."""
    root = Path(root)
    base = os.fspath(extended(root))

    def listed(folder: str, shown: Path) -> Iterator[Path]:
        try:
            with os.scandir(folder) as scan:
                entries = sorted(scan, key=lambda e: e.name.casefold())
        except OSError as exc:
            if errors is None:
                raise
            errors.append(f"{shown} could not be listed ({exc.strerror or exc})")
            return
        for entry in entries:
            here = shown / entry.name
            try:
                linked = entry.is_symlink() or getattr(entry.stat(follow_symlinks=False), "st_reparse_tag", 0) \
                    == 0xA0000003
                folder_entry = entry.is_dir(follow_symlinks=False)
            except OSError as exc:
                if errors is None:
                    raise
                errors.append(f"{here} could not be examined ({exc.strerror or exc})")
                continue
            if linked or (link is not None and link(here)):
                continue
            if folder_entry:
                if skip is not None and skip(here):
                    continue
                yield from listed(os.path.join(folder, entry.name), here)
            else:
                yield here

    if not os.path.isdir(base):
        return
    yield from listed(base, root)


def makedirs(path: os.PathLike | str) -> None:
    os.makedirs(extended(path), exist_ok=True)


def unlink(path: os.PathLike | str) -> None:
    os.unlink(extended(path))


def rmtree(path: os.PathLike | str, onexc=None) -> None:
    if onexc is None:
        shutil.rmtree(extended(path))
    else:
        shutil.rmtree(extended(path), onexc=onexc)
