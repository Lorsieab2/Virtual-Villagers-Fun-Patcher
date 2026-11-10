"""Windows as most players have it: long paths switched OFF.

Where long paths are switched off (the default; the owner's own PC has them
on, so a plain run there cannot see the difference), a path of MAX_PATH (260)
characters or more -- 248 for a new folder -- fails unless it carries the
"\\\\?\\" prefix (src/patcher_files.py long_path). Inside `classic_max_path()`
every file-system call this process makes is held to that rule: opening,
renaming, removing, listing, copying (Python's audit events, which cover
open(), os.open(), os.rename / os.replace, os.remove, os.mkdir, os.rmdir,
os.scandir, os.listdir, os.chmod, os.utime and shutil's CopyFile2), and
os.stat / os.lstat; os.path.isfile / isdir / exists / lexists answer False
for such a path, as Windows does. A call that breaks the rule raises
OSError (ERROR_FILENAME_EXCED_RANGE) and is recorded in `refused`.

Tests only; it never changes Windows' own setting.
"""
from __future__ import annotations

import contextlib
import ntpath
import os
import sys
from typing import Any, Iterator

MAX_PATH = 260
MAX_DIRECTORY = MAX_PATH - 12          # CreateDirectoryW leaves room for an 8.3 name
ERROR_FILENAME_EXCED_RANGE = 206
_PREFIXES = ("\\\\?\\", "\\\\.\\")

_active = False
refused: list[str] = []

# The audit events that name paths, and which of their arguments are paths.
_EVENTS: dict[str, tuple[int, ...]] = {
    "open": (0,),
    "os.rename": (0, 1),
    "os.remove": (0,),
    "os.rmdir": (0,),
    "os.mkdir": (0,),
    "os.scandir": (0,),
    "os.listdir": (0,),
    "os.chmod": (0,),
    "os.utime": (0,),
    "os.truncate": (0,),
    "_winapi.CopyFile2": (0, 1),
}


def too_long(path: Any, limit: int = MAX_PATH) -> bool:
    """Whether Windows with long paths off would refuse `path`."""
    if isinstance(path, int) or path is None:
        return False
    try:
        text = os.fsdecode(path)
    except TypeError:
        return False
    if not text or text.startswith(_PREFIXES):
        return False
    return len(os.path.abspath(text)) >= limit


def _refuse(text: Any, event: str) -> None:
    refused.append(f"{event}: {os.fsdecode(text)}")
    raise OSError(0, "emulated classic MAX_PATH: the path is too long", os.fsdecode(text),
                  ERROR_FILENAME_EXCED_RANGE)


def _audit(event: str, args: tuple) -> None:
    if not _active or event not in _EVENTS:
        return
    limit = MAX_DIRECTORY if event == "os.mkdir" else MAX_PATH
    for index in _EVENTS[event]:
        if index < len(args) and too_long(args[index], limit):
            _refuse(args[index], event)


_hooked = False


@contextlib.contextmanager
def classic_max_path() -> Iterator[list[str]]:
    """Hold every file-system call to the classic limit while inside; yields `refused`."""
    global _active, _hooked
    if os.name != "nt":
        yield refused
        return
    if not _hooked:
        sys.addaudithook(_audit)      # cannot be removed; idle outside the block
        _hooked = True
    saved = {name: getattr(os, name) for name in ("stat", "lstat")}
    saved_path = {name: getattr(ntpath, name) for name in ("isfile", "isdir", "exists", "lexists")}

    def checked(name, real):
        def call(path, *args, **kwargs):
            if too_long(path):
                _refuse(path, f"os.{name}")
            return real(path, *args, **kwargs)
        return call

    def answered(real):
        def call(path, *args, **kwargs):
            return False if too_long(path) else real(path, *args, **kwargs)
        return call

    refused.clear()
    for name, real in saved.items():
        setattr(os, name, checked(name, real))
    for name, real in saved_path.items():
        setattr(ntpath, name, answered(real))
    _active = True
    try:
        yield refused
    finally:
        _active = False
        for name, real in saved.items():
            setattr(os, name, real)
        for name, real in saved_path.items():
            setattr(ntpath, name, real)
