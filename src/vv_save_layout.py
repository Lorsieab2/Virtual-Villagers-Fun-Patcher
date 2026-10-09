"""The names of the folders and files the patcher keeps in a save folder, and the move from the names
older builds used (the owner, 2026-10-09: "rename the patcher-created folders and files to accurately
explain what they contain. and sort things in separate folders, appropriately named too" -- the save
folders only; Tribe History and Tribe Population keep their names).

    Logs\\Deaths                       -> Logs\\Deaths and Disappearances
    Logs\\Repairs                      -> Logs\\Repairs Made
    Logs\\Genealogy                    -> Family Trees\\Reports
    Data\\Genealogy\\... Genealogy Edits -> Data\\Family Tree Edits\\... Family Tree Edits
    Data\\Unaccounted Villagers\\Virtual Villagers G Village Roster
                                      -> ...\\Virtual Villagers G Villagers at Last Save
    Data\\Village Statistics\\Village Roster -> ...\\Villagers Counted
    Data\\Log Words                    -> Data\\Like and Dislike Words
    Data\\Cross-Check                  -> Data\\Log Checks
    Data\\Parentage Records            -> Data\\Parents (A New Home)
    every "<file>.before-..." copy a repair kept beside a log or data file
                                      -> Data\\Copies Made Before Repairs\\<the same place>

The game does the same move when it opens (native/shared/save_layout.h, from "VVFP Startup.dll"),
so a village a player plays is moved before anything is written under the new names.  Here it is
done only by what writes (Repair Saves & Logs, last names, numbering) and only with the game closed;
what only reads (Check Saves & Logs, the Family Tree Maker) finds a file under either name with
`existing`.  Nothing is ever overwritten: a file whose new place is taken stays where it is.  The
Backups folder is never touched."""
from __future__ import annotations

import os
import re
from pathlib import Path

LOGS = "Virtual Villagers Fun Patcher Logs"
DATA = "Virtual Villagers Fun Patcher Data"
TREES = "Virtual Villagers Fun Patcher Family Trees"
COPIES = "Copies Made Before Repairs"

DEATHS_LOGS = "Deaths and Disappearances"
REPAIRS_LOGS = "Repairs Made"
TREE_REPORTS = "Reports"
TREE_EDITS = "Family Tree Edits"
LOG_WORDS = "Like and Dislike Words"
LOG_CHECKS = "Log Checks"
PARENTS_VV1 = "Parents (A New Home)"

# (old folder, new folder), relative to the save folder: each file moved with its place inside.
FOLDERS = (
    (f"{LOGS}\\Deaths", f"{LOGS}\\{DEATHS_LOGS}"),
    (f"{LOGS}\\Repairs", f"{LOGS}\\{REPAIRS_LOGS}"),
    (f"{LOGS}\\Genealogy", f"{TREES}\\{TREE_REPORTS}"),
    (f"{DATA}\\Log Words", f"{DATA}\\{LOG_WORDS}"),
    (f"{DATA}\\Cross-Check", f"{DATA}\\{LOG_CHECKS}"),
    (f"{DATA}\\Parentage Records", f"{DATA}\\{PARENTS_VV1}"),
)
# (folder, old name pattern, new name): files renamed (the folder is the new one when it moved).
FILES = (
    (f"{DATA}\\Genealogy", re.compile(r"^(Virtual Villagers \d) Genealogy Edits( - Save \d+\.json)$"),
     f"{DATA}\\{TREE_EDITS}", r"\1 Family Tree Edits\2"),
    (f"{DATA}\\Unaccounted Villagers", re.compile(r"^(Virtual Villagers \d) Village Roster( - Save \d+\.dat.*)$"),
     f"{DATA}\\Unaccounted Villagers", r"\1 Villagers at Last Save\2"),
    (f"{DATA}\\Village Statistics", re.compile(r"^Village Roster( - Save \d+\.dat.*)$"),
     f"{DATA}\\Village Statistics", r"Villagers Counted\1"),
)
BEFORE_COPY = re.compile(r"\.before-[^\\/]*$")


def _move(source: Path, target: Path) -> bool:
    """`source` to `target` unless `target` is taken; True when it moved."""
    if target.exists():
        return False
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(source, target)
        return True
    except OSError:
        return False


def _remove_if_empty(folder: Path) -> None:
    try:
        folder.rmdir()
    except OSError:
        pass


def migrate(folder: Path) -> list[tuple[Path, Path]]:
    """Move one save folder's patcher files to the names above.  Returns each (from, to) moved.  The
    game must be closed (the callers refuse to write while it runs)."""
    folder = Path(folder)
    moved: list[tuple[Path, Path]] = []
    for old, new in FOLDERS:
        source = folder / old
        if not source.is_dir():
            continue
        for path in sorted(source.rglob("*"), key=lambda p: len(p.parts), reverse=False):
            if path.is_file():
                target = folder / new / path.relative_to(source)
                if _move(path, target):
                    moved.append((path, target))
        for sub in sorted((p for p in source.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
            _remove_if_empty(sub)
        _remove_if_empty(source)
    for old, pattern, new, replacement in FILES:
        source = folder / old
        if not source.is_dir():
            continue
        for path in sorted(source.iterdir()):
            if path.is_file() and pattern.match(path.name):
                target = folder / new / pattern.sub(replacement, path.name)
                if _move(path, target):
                    moved.append((path, target))
        _remove_if_empty(source)
    copies = folder / DATA / COPIES
    for top in (LOGS, DATA):
        root = folder / top
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or not BEFORE_COPY.search(path.name) or copies in path.parents:
                continue
            target = copies / path.relative_to(folder)
            n = 2
            while target.exists():                      # never over an earlier copy of the same name
                target = copies / path.relative_to(folder).with_name(f"{path.name} ({n})")
                n += 1
            if _move(path, target):
                moved.append((path, target))
    return moved


def existing(folder: Path, new: str, old: str) -> Path:
    """The file or folder at `new` (relative to the save folder), or at `old` while it has not moved."""
    folder = Path(folder)
    return folder / new if (folder / new).exists() or not (folder / old).exists() else folder / old


def old_name(relative: str) -> str | None:
    """Where an older build kept the file or folder `relative` (a path under its new name, relative to
    the save folder), or None when its name did not change."""
    rel = relative.replace("/", "\\")
    for old, new in FOLDERS:
        if rel.lower() == new.lower() or rel.lower().startswith(new.lower() + "\\"):
            rel = old + rel[len(new):]
            break
    for old_folder, pattern, new_folder, replacement in FILES:
        head, _, name = rel.rpartition("\\")
        if head.lower() == new_folder.lower():
            back = _FILES_BACK.get(replacement)
            m = back.match(name) if back else None
            if m:
                return f"{old_folder}\\{back.sub(_OLD_NAMES[replacement], name)}"
    return rel if rel != relative.replace("/", "\\") else None


# The new file names back to the old ones (FILES, read the other way).
_FILES_BACK = {
    r"\1 Family Tree Edits\2": re.compile(r"^(Virtual Villagers \d) Family Tree Edits( - Save \d+\.json)$"),
    r"\1 Villagers at Last Save\2": re.compile(r"^(Virtual Villagers \d) Villagers at Last Save( - Save \d+\.dat.*)$"),
    r"Villagers Counted\1": re.compile(r"^Villagers Counted( - Save \d+\.dat.*)$"),
}
_OLD_NAMES = {
    r"\1 Family Tree Edits\2": r"\1 Genealogy Edits\2",
    r"\1 Villagers at Last Save\2": r"\1 Village Roster\2",
    r"Villagers Counted\1": r"Village Roster\1",
}


def find(folder: Path, relative: str) -> Path:
    """`relative` (its new name) in the save folder, or where an older build kept it while it has not
    moved: for what only reads, and for what writes with the game running."""
    old = old_name(relative)
    return existing(folder, relative, old) if old else Path(folder) / relative
