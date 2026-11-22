"""The copies kept before repairs: short names and their index (the owner, 2026-11-20: "files people see
first keep full names, while anything in subfolders gets truncated as short as possible but readable; the
top patcher folders keep full names").

Older builds kept each copy at its file's own place inside "Copies Made Before Repairs", under its full
name and a long reason ("...\\Copies Made Before Repairs\\Logs\\Births and Conceptions\\Virtual Villagers 3
Births and Conceptions Log 1.txt.before-v1.35.85-repair-2"): nested in a long save folder those ran past
Windows' 259 characters.  A NEW copy goes straight into the Copies Made Before Repairs folder (the save's
own, "Virtual Villagers Fun Patcher\\Save <S>\\Data\\Copies Made Before Repairs", for a file of a save's
own folder; else "Virtual Villagers Fun Patcher Data\\Copies Made Before Repairs") under a short name:

    <the file's name without "Virtual Villagers <G> ">.bak<n>      "Parentage Records - Save 1.dat.bak1"

<n> the first number not yet used for that name in the folder.  One line of "Copies Index.txt" in the same
folder says which file it is a copy of (its place in the save folder), why, and when:

    Parentage Records - Save 1.dat.bak1<TAB>Virtual Villagers Fun Patcher\\Save 1\\Data\\Parents (A New
    Home)\\Virtual Villagers 1 Parentage Records - Save 1.dat<TAB>before-parents-restore<TAB>2026-11-20 14:03:11

THE BUDGET.  A new copy's place inside the save folder is at most COPY_RELATIVE_MAX (116) characters, no
longer than the patcher's own longest file there (tests/test_long_paths.py): wherever the patcher's own
files fit, so do its copies.

The older copies stay where they are, under their names; nothing is renamed, moved or deleted, and every
reader reads both (vv_long_paths takes the long ones)."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import vv_long_paths as lp
import vv_save_layout as layout

INDEX = "Copies Index.txt"
_INDEX_HEAD = ("# The copies kept before repairs in this folder: the copy, the file it is a copy of (its place in "
               "the save folder), why, and when.\r\n")
_GAME_PREFIX = re.compile(r"^Virtual Villagers(?: [1-5]| -) ", re.I)
_TRAILING_NUMBER = re.compile(r"-\d+$")
SHORT_MAX = 40                    # the longest short name, before ".bak<n>"
# THE BUDGET: the longest place a new copy can have inside the save folder -- a save's own Copies Made Before
# Repairs, the longest short name and ".bak999".  No longer than the patcher's own longest file there, "Virtual
# Villagers Fun Patcher\Save <S>\Logs\Births and Conceptions\Virtual Villagers <G> Births and Conceptions Log
# <n>.txt" (118 characters for <n> < 10): wherever the patcher's own files fit, so do its copies.
COPY_RELATIVE_MAX = len(f"{layout.SAVES}\\Save 1\\{layout.SAVE_DATA}\\{layout.COPIES}\\") + SHORT_MAX + len(".bak999")
BAK = re.compile(r"^(?P<short>.+)\.bak(?P<n>\d+)$", re.I)


def short_name(name: str) -> str:
    """`name` as short as possible but readable: without "Virtual Villagers <G> " or "Virtual Villagers - "
    (the save folder says the game), and at most SHORT_MAX characters (the end of the stem cut, the
    extension kept)."""
    short = _GAME_PREFIX.sub("", name) or name
    if len(short) <= SHORT_MAX:
        return short
    stem, dot, ext = short.rpartition(".")
    if not dot or not stem or len(ext) > 8:
        return short[:SHORT_MAX].rstrip(" .")
    return stem[:SHORT_MAX - len(ext) - 1].rstrip(" .") + "." + ext


def reason_of(suffix: str) -> str:
    """The reason a caller's copy suffix gives (".before-parents-restore-2" -> "before-parents-restore",
    " (before move to save folder)" -> "before move to save folder"; "" -> "set aside")."""
    text = suffix.strip()
    if text.startswith("(") or text.startswith(".before-"):
        text = _TRAILING_NUMBER.sub("", text)          # the caller's "-<k>"
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1]
    text = text.lstrip(".").strip()
    return text or "set aside"


def copies_folder(folder: Path, path: Path) -> Path:
    """The Copies Made Before Repairs folder a new copy of `path` (in the save folder) goes in."""
    folder = Path(folder)
    relative = Path(path).resolve().relative_to(folder.resolve())
    if layout.older_layout(folder, path) is not None:
        return folder / relative.parts[0] / relative.parts[1] / layout.SAVE_DATA / layout.COPIES
    return folder / layout.DATA / layout.COPIES


def _relative(folder: Path, path: Path) -> str:
    return str(Path(path).resolve().relative_to(Path(folder).resolve()))


@dataclass
class Kept:
    copy: Path                    # the copy
    original: str                 # the file it is a copy of, relative to the save folder
    reason: str
    when: str


def entries(copies: Path) -> list[Kept]:
    """Every line of the folder's index, oldest first (a name given twice: the later line is the one)."""
    index = Path(copies) / INDEX
    try:
        text = lp.read_bytes(index).decode("utf-8", "replace")
    except FileNotFoundError:
        return []
    out: list[Kept] = []
    for line in text.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 2 or not parts[0] or "\\" in parts[0] or "/" in parts[0]:
            continue
        out.append(Kept(Path(copies) / parts[0], parts[1], parts[2] if len(parts) > 2 else "",
                        parts[3] if len(parts) > 3 else ""))
    latest: dict[str, Kept] = {}
    for kept in out:
        latest[kept.copy.name.casefold()] = kept
    return [k for k in out if latest[k.copy.name.casefold()] is k]


def new_copy(folder: Path, path: Path, suffix: str, now: datetime | None = None) -> Path:
    """The place for a new copy of `path` (in the save folder), its folder made and its index line written
    first: "<short name>.bak<n>" in its Copies Made Before Repairs folder, never a name in use.  The caller
    writes the copy there (never replacing a file)."""
    folder = Path(folder)
    copies = copies_folder(folder, path)
    short = short_name(Path(path).name)
    lp.makedirs(copies)
    used = 0
    for kept in entries(copies):
        m = BAK.match(kept.copy.name)
        if m and m.group("short").casefold() == short.casefold():
            used = max(used, int(m.group("n")))
    with os.scandir(lp.extended(copies)) as scan:
        for entry in scan:
            m = BAK.match(entry.name)
            if m and m.group("short").casefold() == short.casefold():
                used = max(used, int(m.group("n")))
    target = copies / f"{short}.bak{used + 1}"
    index = lp.extended(copies / INDEX)
    head = b"" if index.exists() else _INDEX_HEAD.encode("utf-8")
    line = "\t".join((target.name, _relative(folder, path), reason_of(suffix),
                      (now or datetime.now()).strftime("%Y-%m-%d %H:%M:%S"))) + "\r\n"
    with open(index, "ab") as handle:
        handle.write(head + line.encode("utf-8"))
    return target


def _all_copies_folders(folder: Path) -> list[Path]:
    folder = Path(folder)
    return [folder / layout.DATA / layout.COPIES] + [
        folder / layout.save_root(s) / layout.SAVE_DATA / layout.COPIES for s in layout.SLOTS]


def all_kept(folder: Path) -> list[Kept]:
    """Every indexed copy in the save folder that is there (the older layout's folder, then each save's)."""
    out: list[Kept] = []
    for copies in _all_copies_folders(folder):
        out += [k for k in entries(copies) if lp.is_file(k.copy)]
    return out


def kept_copies(folder: Path, path: Path, reason: str | None = None, before_only: bool = False) -> list[Path]:
    """The indexed copies of `path` (in the save folder) that are there -- made at its place now, or at its
    older-layout place before "Move Files to Save Folders..." -- only those made for `reason` when given
    (a caller's suffix or a reason), or with `before_only` only those made before a repair (a reason
    "before-...", as an older build's ".before-..." name said; not a file set aside or copied before a
    move), oldest first."""
    folder = Path(folder)
    try:
        names = {_relative(folder, path).casefold()}
    except ValueError:
        return []
    older = layout.older_layout(folder, path)
    if older is not None:
        names.add(older.casefold())
    wanted = reason_of(reason) if reason is not None else None
    return [k.copy for k in all_kept(folder)
            if k.original.casefold() in names and (wanted is None or k.reason == wanted)
            and (not before_only or k.reason.startswith("before-"))]


def copy_relative(original_relative: str) -> str:
    """Where a new copy of the file at `original_relative` (in the save folder) goes, relative to the save
    folder, with the largest number a folder could need (".bak999"): the budget."""
    parts = original_relative.replace("/", "\\").split("\\")
    if len(parts) >= 3 and parts[0].casefold() == layout.SAVES.casefold() \
            and re.fullmatch(r"(?i)save [1-5]", parts[1]):
        place = f"{parts[0]}\\{parts[1]}\\{layout.SAVE_DATA}\\{layout.COPIES}"
    else:
        place = f"{layout.DATA}\\{layout.COPIES}"
    return f"{place}\\{short_name(parts[-1])}.bak999"


